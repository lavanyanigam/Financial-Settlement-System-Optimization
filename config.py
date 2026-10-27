"""
All configuration settings for the Indian DvP Settlement Optimization.
Directly models the INDEVAL settlement mechanism from Muñoz et al. (2011).
"""

# ---------------------------------------------------------------- Data Files
DATA_DIR = "data"
RAW_TRADES_FILE = "data/Stock_Trades_Orders/Trades .csv"

# Preprocessed from real exchange records
INSTRUCTIONS_FILE = "data/instructions.csv"  # DvP instructions (buyer, seller, ticker, qty, price)
PARTICIPANTS_FILE = "data/participants.csv"  # Real brokers/members (with trading volume weights)
SEC_BAL_FILE = "data/initial_securities.csv"  # Initial stock inventories B_ik
CASH_BAL_FILE = "data/initial_cash.csv"       # Initial cash credit lines C_i
STEP5_FILE = "data/step5_comparison.csv"     # Output of Step 5 comparison
RESULTS_FILE = "data/scenario_results.csv"   # Output of Step 6 scenario grid

SEED = 42

# ---------------------------------------------------------------- Market Timings & Setup
MARKET_OPEN = "09:55:00"
MARKET_CLOSE = "15:30:00"

# ---------------------------------------------------------------- Initial Balances Setup
# B_ik = SECURITY_COVERAGE x (participant i's total sells of stock k during the day)
# Setting this to 0.3 means participants start with 30% of needed stock inventory.
# They must wait for incoming trade deliveries to fulfill subsequent sales,
# testing the LP's ability to untangle settlement gridlocks.
SECURITY_COVERAGE = 0.3

# Cash Setup:
# None = The paper's baseline setup: participants start at zero cash and have intraday
#        central bank overdraft access. The simulation tracks peak negative cash to measure
#        exact liquidity demand.
# 0.15 = Stress test: Credit line capped at 15% of daily purchases.
CASH_COVERAGE = None

# ---------------------------------------------------------------- Paper's 48-Scenario Grid (p. 13)
# 1. Presettlement rules:
#    - "all_to_clearing": all instructions wait in queue for periodic LP clearing
#    - "gross_first"    : settle immediately if both cash and shares are available; else queue
PRESETTLE_RULES = ["all_to_clearing", "gross_first"]

# 2. Optimization objectives:
#    - "value"   : maximize cash value of settled trades (p_l * x_l)
#    - "quantity": maximize total shares settled (x_l)
OBJECTIVES = ["value", "quantity"]

# 3. Value triggers:
#    In the paper: 60,000 / 75,000 million pesos on a ~US$250bn day (~1.8% / 2.3% of daily value).
#    We apply the exact same percentages to the Indian trading day value.
VALUE_TRIGGER_SHARES = [0.018, 0.023]

# 4. Count triggers:
#    In the paper: 250 / 350 instructions (~1.2% / 1.7% of instructions count).
COUNT_TRIGGER_SHARES = [0.012, 0.017]
COUNT_TRIGGERS_ABSOLUTE = None

# 5. Time triggers:
#    Run LP clearing batch every 5, 10, or 15 minutes.
TIME_TRIGGERS_MIN = [5, 10, 15]
