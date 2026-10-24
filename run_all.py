"""
Run every step in order. Use --sample to (re)generate the sample L2 file first.

    python run_all.py --sample     # test the whole pipeline on made-up data
    python run_all.py              # run on YOUR file at config.L2_FILE
"""
import subprocess
import sys

steps = ["step1_l2_to_trades.py", "step2_participants.py", "step3_assign_counterparties.py",
         "step4_initial_balances.py", "step5_netting_benefit.py", "step6_scenarios.py"]
if "--sample" in sys.argv:
    steps.insert(0, "step0_make_sample_l2.py")

for s in steps:
    print("\n" + "=" * 78 + f"\n{s}\n" + "=" * 78)
    if subprocess.run([sys.executable, s]).returncode != 0:
        sys.exit(f"{s} failed - fix the error above and re-run.")
