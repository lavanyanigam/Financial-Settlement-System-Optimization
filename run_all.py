"""
Master script to execute the complete pipeline on the real Indian dataset in sequence:
  1. prep.py                    : Cleans real exchange trades & formats DvP instructions
  2. step4_initial_balances.py  : Sets starting stock coverage (B_ik) & cash lines (C_i)
  3. step5_netting_benefit.py   : Headline comparison (RTGS vs 5-min INDEVAL LP vs EOD Netting)
  4. step6_scenarios.py         : Runs the paper's 48-scenario grid & generates chart

Run:
    python run_all.py
"""
import subprocess
import sys

steps = [
    ("1. Preprocessing Real Indian Trades", "prep.py"),
    ("2. Generating Initial Balances (B_ik and C_i)", "step4_initial_balances.py"),
    ("3. Headline Comparison (RTGS vs LP vs EOD)", "step5_netting_benefit.py"),
    ("4. Full 48-Scenario Simulation Matrix", "step6_scenarios.py"),
]

for title, script in steps:
    print("\n" + "=" * 78)
    print(f"Executing {title} ({script})")
    print("=" * 78)
    res = subprocess.run([sys.executable, script])
    if res.returncode != 0:
        sys.exit(f"\n[ERROR] {script} failed. Please resolve the error above.")

print("\n" + "=" * 78)
print("Pipeline completed successfully!")
print("Outputs generated:")
print("  - data/instructions.csv")
print("  - data/participants.csv")
print("  - data/initial_securities.csv")
print("  - data/initial_cash.csv")
print("  - data/step5_comparison.csv")
print("  - data/scenario_results.csv")
print("  - data/tradeoff_chart.png")
print("=" * 78)
