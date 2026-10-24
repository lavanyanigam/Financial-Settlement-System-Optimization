"""
STEP 6 - the paper's 48-scenario experiment (p.13), on your Indian data.

  2 presettlement rules  x  2 objectives  x  2 value triggers
  x 2 count triggers     x  3 time triggers (5/10/15 min)   = 48 runs

For each run it records average settlement time, cash used, and the global
index (their product), then prints the three "best" settings the paper reports:
  1. fastest average settlement
  2. least cash used
  3. best global index
and draws the time-vs-cash trade-off chart.

Run:  python step6_scenarios.py
Out:  data/scenario_results.csv, data/tradeoff_chart.png
"""
import itertools
from multiprocessing import Pool
import pandas as pd
import config as C
import simulator as S

ins, sec0, cash0 = S.load_inputs()
DAY_VALUE = ins["value"].sum()


def one(args):
    rule, obj, vshare, cnt, tmin = args
    r = S.run(ins, sec0, cash0, rule=rule, objective=obj,
              value_trigger=vshare * DAY_VALUE, count_trigger=cnt, time_trigger_min=tmin)
    r["value_trigger_share"] = vshare
    return r


def main():
    counts = C.COUNT_TRIGGERS_ABSOLUTE or [max(1, round(s * len(ins))) for s in C.COUNT_TRIGGER_SHARES]
    grid = list(itertools.product(C.PRESETTLE_RULES, C.OBJECTIVES, C.VALUE_TRIGGER_SHARES,
                                  counts, C.TIME_TRIGGERS_MIN))
    print(f"Running {len(grid)} scenarios on {len(ins):,} instructions "
          f"(day value INR {DAY_VALUE / 1e7:,.1f} crore)")
    print(f"  value triggers: {[float(round(s * DAY_VALUE / 1e7, 2)) for s in C.VALUE_TRIGGER_SHARES]} crore"
          f" | count triggers: {counts} | time triggers: {C.TIME_TRIGGERS_MIN} min")
    with Pool() as pool:
        rows = pool.map(one, grid)
    res = pd.DataFrame(rows)
    res["global_index"] = (res["avg_settle_min"] * res["cash_used_cr"]).round(2)
    res.insert(0, "scenario", range(1, len(res) + 1))
    res.to_csv(C.RESULTS_FILE, index=False)
    print(f"Saved -> {C.RESULTS_FILE}\n")

    settings = ["rule", "objective", "value_trigger_cr", "count_trigger", "time_trigger_min"]
    show = settings + ["avg_settle_min", "cash_used_cr", "global_index", "pct_value_settled"]
    for title, col in [("1. Fastest average settlement", "avg_settle_min"),
                       ("2. Least cash used", "cash_used_cr"),
                       ("3. Best global index (time x cash)", "global_index")]:
        best = res.sort_values([col, "pct_value_settled"], ascending=[True, False]).iloc[0]
        print(title)
        print("   " + "  ".join(f"{k}={best[k]}" for k in show))
    print("\nAverage effect of each setting (mean over the other settings):")
    for s in ["rule", "objective", "value_trigger_cr", "count_trigger", "time_trigger_min"]:
        print(res.groupby(s)[["avg_settle_min", "cash_used_cr", "pct_value_settled"]]
                 .mean().round(2).to_string(), "\n")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(7.5, 5))
        colors = {5: "#1f77b4", 10: "#ff7f0e", 15: "#2ca02c"}
        for tmin, g in res.groupby("time_trigger_min"):
            for rule, mk in [("all_to_clearing", "o"), ("gross_first", "^")]:
                h = g[g["rule"] == rule]
                ax.scatter(h["avg_settle_min"], h["cash_used_cr"], c=colors.get(tmin, "grey"),
                           marker=mk, alpha=.8, label=f"{tmin} min, {rule}")
        ax.set_xlabel("Average settlement time (minutes)")
        ax.set_ylabel("Cash used (INR crore)")
        ax.set_title("Settlement speed vs liquidity: 48 scenarios")
        ax.legend(fontsize=8)
        ax.grid(alpha=.3)
        fig.tight_layout()
        fig.savefig("data/tradeoff_chart.png", dpi=150)
        print("Chart -> data/tradeoff_chart.png")
    except ImportError:
        print("(install matplotlib to get the chart)")


if __name__ == "__main__":
    main()
