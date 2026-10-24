"""
All the knobs for the project live here.
Change these, then re-run the steps. Nothing else needs editing for a first run.
"""

# ---------------------------------------------------------------- files
DATA_DIR = "data"
L2_FILE = "data/l2_orderbook.csv"          # <- put your real L2 export here
TRADES_FILE = "data/trades.csv"             # output of step 1
PARTICIPANTS_FILE = "data/participants.csv" # output of step 2
INSTRUCTIONS_FILE = "data/instructions.csv" # output of step 3 (trades + seller/buyer)
SEC_BAL_FILE = "data/initial_securities.csv"  # output of step 4 (B_ik)
CASH_BAL_FILE = "data/initial_cash.csv"       # output of step 4 (C_i)
RESULTS_FILE = "data/scenario_results.csv"    # output of step 6

SEED = 42

# ---------------------------------------------------------------- step 1: reading your L2 file
# Rename YOUR column names (left) to the names the code expects (right).
# Leave a line out if your file already uses the expected name.
# Expected: timestamp, ticker, bid_px_1..N, bid_sz_1..N, ask_px_1..N, ask_sz_1..N
# Optional (makes inference much better): last_px, last_sz, volume (cumulative day volume)
COLUMN_MAP = {
    # "Date/Time": "timestamp",
    # "Security": "ticker",
    # "BID_PRICE_1": "bid_px_1",
    # "BID_SIZE_1": "bid_sz_1",
    # "ASK_PRICE_1": "ask_px_1",
    # "ASK_SIZE_1": "ask_sz_1",
}
BOOK_LEVELS = 5            # how many depth levels your file has (1 is enough to work)

# "auto"        : use last_px/last_sz if present, else book diffs (+volume check if present)
# "prints"      : only use last_px / last_sz / volume columns
# "book_volume" : book diffs, kept only when cumulative volume also went up
# "book_only"   : book diffs only (cancellations will be mistaken for trades)
INFERENCE_MODE = "auto"

# Real NSE days have hundreds of thousands of trades. Aggregating them into
# buckets keeps the LP small. 0 = no aggregation, 60 = one instruction per
# ticker per side per minute.
AGGREGATE_SECONDS = 0

# ---------------------------------------------------------------- step 2: participants
N_PARTICIPANTS = 30
PARTICIPANT_TYPES = {      # type: share of participants
    "Bank": 0.30,
    "MutualFund": 0.25,
    "Insurer": 0.10,
    "Broker": 0.25,
    "FPI": 0.10,
}
PARETO_ALPHA = 1.5         # lower = more concentrated (a few very big players)

# ---------------------------------------------------------------- step 4: starting balances
# B_ik = SECURITY_COVERAGE x (participant i's total sells of k during the day)
# Cash, two options:
#   CASH_COVERAGE = None -> the paper's set-up: everyone starts with zero cash and
#                           can borrow without limit; the simulator measures how
#                           much borrowing (liquidity) each design needs.
#   CASH_COVERAGE = 0.15 -> stress test: each participant gets a credit line of
#                           15% of its day's buys, so cash can also run out.
SECURITY_COVERAGE = 0.3
CASH_COVERAGE = None

# ---------------------------------------------------------------- step 6: scenario grid (paper p.13)
PRESETTLE_RULES = ["all_to_clearing", "gross_first"]
OBJECTIVES = ["value", "quantity"]          # max cash value vs max number of securities
# Paper: 60,000 / 75,000 million pesos on a ~US$250bn day (about 1.8% / 2.3% of the
# day's value). We set the INR triggers as the same shares of YOUR day's value.
VALUE_TRIGGER_SHARES = [0.018, 0.023]
# Paper: 250 / 350 instructions. The right number depends on how many instructions
# your day has, so we also set it as a share of the day's instruction count
# (1.2% and 1.7% keep the 250:350 ratio and make it compete with the value trigger).
# To use the paper's raw numbers instead, set COUNT_TRIGGERS_ABSOLUTE = [250, 350].
COUNT_TRIGGER_SHARES = [0.012, 0.017]
COUNT_TRIGGERS_ABSOLUTE = None
TIME_TRIGGERS_MIN = [5, 10, 15]

MARKET_OPEN = "09:55:00"
MARKET_CLOSE = "15:30:00"
