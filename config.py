# every setting for the project lives here, so the other scripts just import this file.
# the model itself is the INDEVAL settlement engine from Muñoz et al. (2011).

# file paths
DATA_DIR = "data"
RAW_TRADES_FILE = "data/Stock_Trades_Orders/Trades .csv"   # the trade log from the mendeley dataset

INSTRUCTIONS_FILE = "data/instructions.csv"   # one DvP instruction per trade, made by prep.py
PARTICIPANTS_FILE = "data/participants.csv"   # the broker member codes and their share of traded value
SEC_BAL_FILE = "data/initial_securities.csv"  # opening shares B_ik
CASH_BAL_FILE = "data/initial_cash.csv"       # opening cash / credit lines C_i
STEP5_FILE = "data/step5_comparison.csv"
RESULTS_FILE = "data/scenario_results.csv"
CHART_FILE = "data/tradeoff_chart.png"

# the exchange opened at 09:55 back in 2007, and we cut the day off at the 15:30 close
MARKET_OPEN = "09:55:00"
MARKET_CLOSE = "15:30:00"

# opening shares: each member starts with this fraction of what it sells of a stock that day.
# below 1.0 some sales can only go through after the seller receives shares from another
# trade, which is exactly where batch clearing beats settling one trade at a time.
SECURITY_COVERAGE = 0.3

# opening cash: None is the paper's set-up, where everyone starts at zero with unlimited
# overdraft and we just measure how much each member had to borrow at its worst point.
# set it to something like 0.15 to cap each member's credit at 15% of its buys for the day.
CASH_COVERAGE = None

# the paper's 48-scenario grid (p. 13)

# "all_to_clearing" sends everything to the queue and waits for the LP,
# "gross_first" settles a trade straight away if the shares and cash are there, else queues it
PRESETTLE_RULES = ["all_to_clearing", "gross_first"]

# "value" maximises the rupee value settled, "quantity" maximises the number of shares settled
OBJECTIVES = ["value", "quantity"]

# the paper uses 60,000 / 75,000 million pesos on a roughly US$250bn day, which is about
# 1.8% / 2.3% of the day's value, so we take the same fractions of our day's value
VALUE_TRIGGER_SHARES = [0.018, 0.023]

# the paper uses 250 / 350 instructions but never says how many INDEVAL sees in a day, so
# these fractions are our own choice. they keep the 250:350 ratio and are big enough to
# compete with the value trigger. set COUNT_TRIGGERS_ABSOLUTE = [250, 350] to use the raw numbers.
COUNT_TRIGGER_SHARES = [0.012, 0.017]
COUNT_TRIGGERS_ABSOLUTE = None

# run a clearing every 5, 10 or 15 minutes
TIME_TRIGGERS_MIN = [5, 10, 15]
