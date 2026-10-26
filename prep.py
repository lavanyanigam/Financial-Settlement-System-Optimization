import numpy as np
import pandas as pd

SRC = "data/Stock_Trades_Orders/Trades .csv"
OUT = "data"
DATE = None          # None = busiest day by value; or set e.g. "13-Apr-07"
OPEN, CLOSE = "09:55", "15:30"

t = pd.read_csv(SRC, dtype=str)
t.columns = [c.strip().upper() for c in t.columns]
t = t.apply(lambda col: col.str.strip())
t["qty"] = t["TRADE_QUANTITY"].astype(float).astype(int)
t["price"] = t["TRADE_RATE"].astype(float) / 100          # paise -> rupees
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

# no usable clock time in this file: keep the file's order (TRADE_SEQUENCE)
# and spread the trades evenly across the session
t["SEQ"] = t["TRADE_SEQUENCE"].astype(int)
t = t.sort_values("SEQ").reset_index(drop=True)
start = pd.to_datetime(f"{DATE} {OPEN}", format="%d-%b-%y %H:%M")
end = pd.to_datetime(f"{DATE} {CLOSE}", format="%d-%b-%y %H:%M")
n = len(t)
t["timestamp"] = start + pd.to_timedelta(np.linspace(0, (end - start).total_seconds(), n), unit="s")
print(f"\ntrades: {n:,} | first: {t['timestamp'].min()} | last: {t['timestamp'].max()}")

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