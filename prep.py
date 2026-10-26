import pandas as pd

SRC = "data/Stock_Trades_Orders/Trades .csv"
OUT = "data"
DATE = None          # None = busiest day by value; or set e.g. "13-Apr-07"
OPEN_HOUR = 9        # 09:55 open in 2007

t = pd.read_csv(SRC, dtype=str)
t.columns = [c.strip().upper() for c in t.columns]
t = t.apply(lambda col: col.str.strip())
t["qty"] = t["TRADE_QUANTITY"].astype(float).astype(int)
t["price"] = t["TRADE_RATE"].astype(float) / 100          # paise -> rupees
t["val"] = t["qty"] * t["price"]

# which days are in the file?
daily = (t.groupby("TRADE_DATE")
          .agg(trades=("qty", "size"), value_cr=("val", lambda s: round(s.sum() / 1e7, 1))))
daily = daily.sort_values("value_cr", ascending=False)
print("Trading days in file (busiest first):")
print(daily.to_string())

if DATE is None:
    DATE = daily.index[0]
print(f"\nUsing day: {DATE}")
t = t[t["TRADE_DATE"] == DATE].copy()

# rebuild the missing hour, using TRADE_SEQUENCE order within this one day
t["NUM"] = t["TRADE_NUMBER"].astype(int)
t = t.sort_values("NUM").reset_index(drop=True)
mmss = t["TRADE_TIME"].str.split(":", expand=True)
sec = mmss[0].astype(int) * 60 + mmss[1].astype(float)
jumps = sec.diff()
print("hour wraps:", int((jumps < -1800).sum()))
print("bad backward jumps (should be ~0):", int(((jumps < -1) & (jumps >= -1800)).sum()))
wraps = (sec.diff() < -1800).cumsum()                     # mm:ss jumped back -> new hour
first_min = sec.iloc[0] / 60
hour = OPEN_HOUR + (1 if first_min < 55 else 0) + wraps
day = pd.to_datetime(DATE, format="%d-%b-%y")
t["timestamp"] = day + pd.to_timedelta(hour, unit="h") + pd.to_timedelta(sec, unit="s")

# checks: must sit inside the trading session
print(f"\nfirst trade: {t['timestamp'].min()} | last trade: {t['timestamp'].max()}")
print("trades per hour:")
print(t["timestamp"].dt.hour.value_counts().sort_index().to_string())
if t["timestamp"].min().hour < 9 or t["timestamp"].max().strftime("%H:%M") > "15:30":
    print("WARNING: timestamps fall outside 09:55-15:30. Check the hour rebuild before continuing.")

# build settlement instructions
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

# participants = brokers, weighted by traded value
v = pd.concat([ins.groupby("buyer")["value"].sum(), ins.groupby("seller")["value"].sum()]).groupby(level=0).sum()
parts = pd.DataFrame({"participant": v.index, "type": "Member", "activity_weight": (v / v.sum()).round(6).values})
parts.sort_values("activity_weight", ascending=False).to_csv(f"{OUT}/participants.csv", index=False)

print(f"\nwrote {len(ins):,} instructions and {len(parts)} brokers to {OUT}/")
print(f"day value: Rs {ins['value'].sum() / 1e7:,.1f} crore")