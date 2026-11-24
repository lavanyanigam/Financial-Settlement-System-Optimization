# runs the whole pipeline in order: prep, opening balances, the three-design
# comparison and then the 48 scenarios. just do: python run_all.py
import subprocess
import sys

steps = [
    ("prep: raw trades to DvP instructions", "prep.py"),
    ("step 4: opening balances B_ik and C_i", "step4_initial_balances.py"),
    ("step 5: RTGS vs LP every 5 min vs LP at end of day", "step5_netting_benefit.py"),
    ("step 6: the 48 scenarios", "step6_scenarios.py"),
]

for title, script in steps:
    print("\n" + "=" * 78)
    print(f"{title} ({script})")
    print("=" * 78, flush=True)
    res = subprocess.run([sys.executable, script])
    if res.returncode != 0:
        sys.exit(f"\n{script} failed, see the error above")

print("\n" + "=" * 78)
print("done. outputs are in data/:")
for f in ["instructions.csv", "participants.csv", "initial_securities.csv", "initial_cash.csv",
          "step5_comparison.csv", "scenario_results.csv", "tradeoff_chart.png"]:
    print(f"  data/{f}")
