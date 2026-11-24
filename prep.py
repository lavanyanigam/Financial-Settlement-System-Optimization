# turns the raw mendeley trade log into DvP settlement instructions.
#
# reads  data/Stock_Trades_Orders/Trades .csv  (7 trading days from 2007)
# writes data/instructions.csv    one instruction per trade: seller, buyer, ticker, qty, price, time
#        data/participants.csv    the broker members and their share of the day's traded value
#
# run it with: python prep.py
import pandas as pd
import config as C

DATE = None          # leave as None for the busiest day by value, or set something like "19-Jul-07"

t = pd.read_csv(C.RAW_TRADES_FILE, dtype=str)
# the headers and values come with stray spaces, so we strip everything first
t.columns = [c.strip().upper() for c in t.columns]
t = t.apply(lambda col: col.str.strip())
t["qty"] = t["TRADE_QUANTITY"].astype(float).astype(int)
t["price"] = t["TRADE_RATE"].astype(float) / 100          # the rate is in paise, so this gives rupees
t["val"] = t["qty"] * t["price"]

daily = (t.groupby("TRADE_DATE")
          .agg(trades=("qty", "size"), value_cr=("val", lambda s: round(s.sum() / 1e7, 1))))
daily = daily.sort_values("value_cr", ascending=False)
print("Trading days in file (busiest first):")
print(daily.to_string())
if DATE is None:
    DATE = daily.index[0]
print(f"\nUsing day: {DATE}")
t = t[t["TRADE_DATE"] == DATE].copy()

# TRADE_TIME only has mm:ss.s because the hour got lost in the export. if we walk through
# the trades in TRADE_SEQUENCE order, the minutes wrap back to 00 every new hour, so a
# backward jump of more than 30 minutes means we add an hour. right around the hour the
# sequence can flip between scrips (like 59:46, 00:00.3, 59:46), so a forward jump of more
# than 30 minutes takes that hour back off again.
t["SEQ"] = t["TRADE_SEQUENCE"].astype(int)
t = t.sort_values("SEQ").reset_index(drop=True)
mmss = t["TRADE_TIME"].str.split(":", expand=True)
sec = mmss[0].astype(int) * 60 + mmss[1].astype(float)
jump = sec.diff().fillna(0)
open_h, open_m = (int(x) for x in C.MARKET_OPEN.split(":")[:2])
first_hour = open_h + int(sec.iloc[0] < open_m * 60)
hour = first_hour + ((jump < -1800).astype(int) - (jump > 1800).astype(int)).cumsum()
day = pd.to_datetime(DATE, format="%d-%b-%y")
t["timestamp"] = day + pd.to_timedelta(hour, unit="h") + pd.to_timedelta(sec, unit="s")

# sanity check: inside each scrip, trade numbers go up with time, so the rebuilt
# times should never run backwards when we sort by TRADE_NUMBER
backwards = 0
for _, g in t.assign(tn=t["TRADE_NUMBER"].astype(int)).sort_values("tn").groupby("SCRIP_CODE"):
    backwards += int((g["timestamp"].diff().dt.total_seconds() < -60).sum())
print(f"rebuilt times: {t['timestamp'].min()} to {t['timestamp'].max()} | "
      f"steps going backwards within a scrip: {backwards} (should be 0)")

late = t["timestamp"] > day + pd.Timedelta(C.MARKET_CLOSE)
print(f"dropping {late.sum():,} trades after the {C.MARKET_CLOSE} close")
t = t[~late]
# if the same broker is on both sides there's nothing to settle
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
ins.to_csv(C.INSTRUCTIONS_FILE, index=False)

# the participants are the broker members, since they're the ones who settle with the
# depository, just like INDEVAL's participants. we also keep each one's share of the day's value.
v = pd.concat([ins.groupby("buyer")["value"].sum(), ins.groupby("seller")["value"].sum()]).groupby(level=0).sum()
parts = pd.DataFrame({"participant": v.index, "activity_weight": (v / v.sum()).round(6).values})
parts.sort_values("activity_weight", ascending=False).to_csv(C.PARTICIPANTS_FILE, index=False)

print(f"\nwrote {len(ins):,} instructions and {len(parts)} brokers to {C.DATA_DIR}/")
print(f"day value: Rs {ins['value'].sum() / 1e7:,.1f} crore")
print("instructions per hour:")
print(ins.groupby(pd.to_datetime(ins["timestamp"]).dt.hour).size().to_string())
