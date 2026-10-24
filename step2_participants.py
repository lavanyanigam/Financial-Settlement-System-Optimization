"""
STEP 2 - create the synthetic market participants (the i and j in the paper).

Each participant gets a type (bank, mutual fund, ...) and an ACTIVITY WEIGHT
drawn from a Pareto distribution, so a few big players do most of the trading,
as in real markets. If you have real names (e.g. from NSE bulk/block deals or
Bloomberg HDS holder lists) you can type them into data/participants.csv by hand
instead and keep the same columns.

Run:  python step2_participants.py
Out:  data/participants.csv  (participant, type, activity_weight)
"""
import numpy as np
import pandas as pd
import config as C

rng = np.random.default_rng(C.SEED)

types = []
for t, share in C.PARTICIPANT_TYPES.items():
    types += [t] * int(round(share * C.N_PARTICIPANTS))
types = (types + list(C.PARTICIPANT_TYPES))[:C.N_PARTICIPANTS]   # pad/trim to exact N
rng.shuffle(types)

w = rng.pareto(C.PARETO_ALPHA, C.N_PARTICIPANTS) + 1
w = w / w.sum()

p = pd.DataFrame({
    "participant": [f"P{n:02d}_{t}" for n, t in enumerate(types, start=1)],
    "type": types,
    "activity_weight": w.round(5),
}).sort_values("activity_weight", ascending=False).reset_index(drop=True)
p.to_csv(C.PARTICIPANTS_FILE, index=False)

top5 = p["activity_weight"].head(5).sum()
print(f"Wrote {len(p)} participants -> {C.PARTICIPANTS_FILE}")
print(f"Top 5 participants carry {top5:.0%} of activity\n")
print(p.to_string(index=False))
