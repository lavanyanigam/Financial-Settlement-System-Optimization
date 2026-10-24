"""
STEP 4 - starting balances for each participant.

  B_ik (securities): participant i starts the day holding
        SECURITY_COVERAGE x (everything i sells of stock k today).
        Below 1.0, some sales can only be delivered after i receives those
        shares from a purchase. Settling one trade at a time then gets stuck,
        while settling a batch together (the LP) can untangle the chain.

  C_i  (cash):
        CASH_COVERAGE = None  -> paper's set-up: cash starts at zero and
                                 borrowing is unlimited (stored as a huge
                                 credit line). The simulator records the peak
                                 amount each participant had to borrow; the
                                 total is "the amount of money required to
                                 settle transactions".
        CASH_COVERAGE = 0.15  -> each participant's credit line is 15% of its
                                 day's buys, so cash can run out too.

SECURITY_COVERAGE and CASH_COVERAGE are your main experiment knobs.

Run:  python step4_initial_balances.py
Out:  data/initial_securities.csv (participant, ticker, qty)
      data/initial_cash.csv       (participant, cash_inr)
"""
import numpy as np
import pandas as pd
import config as C

UNLIMITED = 1e15   # INR; effectively "no limit"

ins = pd.read_csv(C.INSTRUCTIONS_FILE)
parts = pd.read_csv(C.PARTICIPANTS_FILE)["participant"]

sells = ins.groupby(["seller", "ticker"])["qty"].sum()
B = np.floor(sells * C.SECURITY_COVERAGE).astype(int).rename("qty").reset_index()
B = B.rename(columns={"seller": "participant"})
B.to_csv(C.SEC_BAL_FILE, index=False)

buys = ins.groupby("buyer")["value"].sum().reindex(parts, fill_value=0)
if C.CASH_COVERAGE is None:
    cash_vals = np.full(len(parts), UNLIMITED)
    cash_note = "unlimited borrowing from zero (paper's set-up)"
else:
    cash_vals = (buys.to_numpy() * C.CASH_COVERAGE).round(2)
    cash_note = (f"credit lines = {C.CASH_COVERAGE:.0%} of buys, total INR "
                 f"{cash_vals.sum() / 1e7:,.1f} crore")
cash = pd.DataFrame({"participant": parts.to_numpy(), "cash_inr": cash_vals})
cash.to_csv(C.CASH_BAL_FILE, index=False)

print(f"Securities: each participant starts with {C.SECURITY_COVERAGE:.0%} of what it sells today")
print(f"  -> {len(B):,} holdings rows written to {C.SEC_BAL_FILE}")
print(f"Cash: {cash_note}")
print(f"  -> {len(cash)} rows written to {C.CASH_BAL_FILE}")
