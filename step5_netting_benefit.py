# step 5 shows why the clearing LP helps, before we run the whole scenario grid.
#
# part A works out how much cash and stock you'd need to settle every trade if nothing
# were netted (each trade settled on arrival with unlimited credit), compared with
# netting everything at the end of the day.
#
# part B runs the same day three ways with the same opening balances:
#   gross_only      model 1 / RTGS, one trade at a time, retried every minute
#   LP every 5 min  INDEVAL-style clearing with P2 + P3
#   LP once at EOD  a classic once-a-day model 3 system
# this is our version of the paper's "52% less liquidity" result.
#
# run it with: python step5_netting_benefit.py
from collections import defaultdict
import pandas as pd
import config as C
import simulator as S

ins, sec0, cash0 = S.load_inputs()

# part A: running cash and share positions, with the peak for every member
cum, peak = defaultdict(float), defaultdict(float)
scum, speak = defaultdict(float), defaultdict(float)
for r in ins.itertuples():
    cum[r.buyer] += r.value; cum[r.seller] -= r.value
    peak[r.buyer] = max(peak[r.buyer], cum[r.buyer])
    scum[(r.seller, r.ticker)] += r.qty; scum[(r.buyer, r.ticker)] -= r.qty
    speak[(r.seller, r.ticker)] = max(speak[(r.seller, r.ticker)], scum[(r.seller, r.ticker)])
gross_cash = sum(peak.values())
net_cash = sum(max(v, 0) for v in cum.values())
gross_sec = sum(speak.values())
net_sec = sum(max(v, 0) for v in scum.values())
print("PART A - resources needed to settle EVERY trade")
print(f"  Cash  : RTGS on arrival INR {gross_cash / 1e7:8.1f} cr | end-of-day net INR {net_cash / 1e7:8.1f} cr"
      f" | saving {1 - net_cash / gross_cash:.0%}")
print(f"  Shares: RTGS on arrival {gross_sec:12,.0f} | end-of-day net {net_sec:12,.0f}"
      f" | saving {1 - net_sec / gross_sec:.0%}")

# part B
print("\nPART B - same starting balances, three settlement designs")
runs = [
    ("RTGS / gross only (retry every 1 min)", dict(rule="gross_only", time_trigger_min=1)),
    ("LP clearing every 5 min (INDEVAL)",       dict(rule="all_to_clearing", time_trigger_min=5)),
    ("LP clearing once at end of day",          dict(rule="all_to_clearing")),
]
rows = []
for name, kw in runs:
    r = S.run(ins, sec0, cash0, **kw)
    rows.append({"design": name, **{k: r[k] for k in
                 ["pct_trades_settled", "pct_value_settled", "avg_settle_min", "cash_used_cr",
                  "clearings", "avg_lp_seconds", "trust_peak_pct_of_day"]}})
res = pd.DataFrame(rows).set_index("design")
print(res.T.to_string())
res.to_csv(C.STEP5_FILE)
print(f"\nSaved -> {C.STEP5_FILE}")
