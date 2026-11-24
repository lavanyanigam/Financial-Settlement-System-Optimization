# step 4 sets up each member's opening balances.
#
# shares (B_ik): member i starts the day holding SECURITY_COVERAGE times everything it
# sells of stock k today. below 1.0 some sales can only be delivered once i has received
# those shares from a purchase, so settling one trade at a time gets stuck while settling
# a batch together with the LP can untangle the chain.
#
# cash (C_i): with CASH_COVERAGE = None we follow the paper, so cash starts at zero and
# borrowing is unlimited (we store it as a huge credit line). the simulator then records
# the most each member had to borrow, and the total is the paper's "amount of money
# required to settle transactions". with CASH_COVERAGE = 0.15 each member's credit line
# is 15% of its buys for the day, so cash can run out as well.
#
# run it with: python step4_initial_balances.py
# writes data/initial_securities.csv (participant, ticker, qty)
#    and data/initial_cash.csv (participant, cash_inr)
import numpy as np
import pandas as pd
import config as C

UNLIMITED = 1e15   # rupees, big enough that it never runs out

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
