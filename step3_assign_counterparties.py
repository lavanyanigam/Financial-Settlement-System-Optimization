"""
STEP 3 - give every trade a seller (i) and a buyer (j).

Rules:
  * seller and buyer are drawn at random, weighted by activity_weight;
  * seller != buyer;
  * every participant can buy AND sell the same stock during the day. This is
    what creates chains (A->B->C->A) that netting can exploit. Without it, the
    clearing LP would have nothing to optimise.

Each row of the output is one DvP settlement instruction: participant i
delivers qty shares of security k to participant j against qty x price rupees.
In the paper's notation: L_ijkl = qty, p_ijkl = price, l = trade_id.

Run:  python step3_assign_counterparties.py
Out:  data/instructions.csv
"""
import numpy as np
import pandas as pd
import config as C

rng = np.random.default_rng(C.SEED + 3)

trades = pd.read_csv(C.TRADES_FILE, parse_dates=["timestamp"])
parts = pd.read_csv(C.PARTICIPANTS_FILE)
names = parts["participant"].to_numpy()
w = parts["activity_weight"].to_numpy()
w = w / w.sum()

n = len(trades)
seller = rng.choice(len(names), size=n, p=w)
buyer = rng.choice(len(names), size=n, p=w)
same = seller == buyer
while same.any():                       # redraw buyers that equal the seller
    buyer[same] = rng.choice(len(names), size=same.sum(), p=w)
    same = seller == buyer

ins = trades.copy()
ins["seller"] = names[seller]
ins["buyer"] = names[buyer]
ins = ins[["trade_id", "timestamp", "ticker", "seller", "buyer", "qty", "price", "value", "side"]]
ins = ins.rename(columns={"side": "aggressor_side"})
ins.to_csv(C.INSTRUCTIONS_FILE, index=False)

# quick look: how much offsetting is there?
gross = ins["value"].sum()
pos = pd.concat([
    ins.groupby("buyer")["value"].sum().rename("bought"),
    ins.groupby("seller")["value"].sum().rename("sold"),
], axis=1).fillna(0)
net = (pos["bought"] - pos["sold"]).clip(lower=0).sum()
print(f"Wrote {len(ins):,} settlement instructions -> {C.INSTRUCTIONS_FILE}")
print(f"Gross value to settle : INR {gross / 1e7:,.1f} crore")
print(f"Net cash after netting: INR {net / 1e7:,.1f} crore  "
      f"({1 - net / gross:.0%} of gross cash could be netted away)")
print("\nFirst rows:")
print(ins.head(8).to_string(index=False))
