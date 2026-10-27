import pandas as pd

SRC = "/Users/lavanyanigam/Downloads/Stock_Trades_Orders/Trades .csv"
OUT = "data"          # the project's data folder
OPEN_HOUR = 9         # BSE/NSE opened at 09:55 in 2007
DAY = "13-Apr-07"     # the file holds 7 dates; the simulator replays ONE day
CLOSE = "15:30:00"    # trades stamped after this (post-close session) are dropped

t = pd.read_csv(SRC, dtype=str)
t.columns = [c.strip().upper() for c in t.columns]          # clean the messy headers
t = t.apply(lambda col: col.str.strip())
print("rows:", len(t), "| dates:", list(t["TRADE_DATE"].unique()), "| scrips:", t["SCRIP_CODE"].nunique(),
      "| members:", pd.concat([t["BUY_MEMBER_CODE"], t["SELL_MEMBER_CODE"]]).nunique())
t = t[t["TRADE_DATE"] == DAY]
print(f"keeping {DAY} only: {len(t):,} trades")

# ---- rebuild the missing hour: walk through trades in sequence order,
#      and add 1 hour every time mm:ss jumps backwards (e.g. 59:58 -> 00:03).
#      TRADE_SEQUENCE is not strictly time-ordered across scrips near the hour
#      (e.g. 59:46, 00:00.3, 59:46), so a forward jump of >30 min takes the
#      hour back off again; otherwise those flips add spurious hours.
t["SEQ"] = t["TRADE_SEQUENCE"].astype(int)
t = t.sort_values(["TRADE_DATE", "SEQ"]).reset_index(drop=True)
mmss = t["TRADE_TIME"].str.split(":", expand=True)
sec = mmss[0].astype(int) * 60 + mmss[1].astype(float)
wraps = sec.groupby(t["TRADE_DATE"]).transform(lambda s: ((s.diff() < -1800).astype(int) - (s.diff() > 1800).astype(int)).cumsum())
first_min = sec.groupby(t["TRADE_DATE"]).transform("first") / 60
hour = OPEN_HOUR + (first_min < 55).astype(int) + wraps
day = pd.to_datetime(t["TRADE_DATE"], format="%d-%b-%y")
t["timestamp"] = day + pd.to_timedelta(hour, unit="h") + pd.to_timedelta(sec, unit="s")
late = t["timestamp"] > day + pd.Timedelta(CLOSE)
print(f"dropping {late.sum():,} trades stamped after {CLOSE}")
t = t[~late]
print("first trade:", t["timestamp"].min(), "| last trade:", t["timestamp"].max())

# ---- build the settlement instructions
t["qty"] = t["TRADE_QUANTITY"].astype(float).astype(int)
t["price"] = t["TRADE_RATE"].astype(float) / 100           # assumes rate is in paise (13740 = Rs 137.40)
same = t["BUY_MEMBER_CODE"] == t["SELL_MEMBER_CODE"]
print(f"dropping {same.sum():,} trades where buyer and seller are the same broker")
t = t[~same & (t["qty"] > 0)].sort_values("timestamp", kind="stable")

ins = pd.DataFrame({
    "trade_id": range(1, len(t) + 1),
    "timestamp": t["timestamp"].values,
    "ticker": t["SCRIP_CODE"].values,
    "seller": "M" + t["SELL_MEMBER_CODE"].values,
    "buyer": "M" + t["BUY_MEMBER_CODE"].values,
    "qty": t["qty"].values,
    "price": t["price"].values,
})
ins["value"] = ins["qty"] * ins["price"]
ins["aggressor_side"] = "na"
ins.to_csv(f"{OUT}/instructions.csv", index=False)

# participants = brokers, weighted by how much they traded
v = pd.concat([ins.groupby("buyer")["value"].sum(), ins.groupby("seller")["value"].sum()]).groupby(level=0).sum()
parts = pd.DataFrame({"participant": v.index, "type": "Member", "activity_weight": (v / v.sum()).round(6).values})
parts.sort_values("activity_weight", ascending=False).to_csv(f"{OUT}/participants.csv", index=False)

print(f"\nwrote {len(ins):,} instructions and {len(parts)} brokers to {OUT}/")
print(f"day value: Rs {ins['value'].sum() / 1e7:,.1f} crore")
print(ins.head())