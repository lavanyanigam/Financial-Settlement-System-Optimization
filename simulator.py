"""
The settlement-system simulator (paper Figure 1: presettlement -> clearing -> settlement).

Instructions arrive one at a time in time order (like the paper, we replay one
real busy day rather than simulating random arrivals).

  Presettlement rule
    "all_to_clearing": every instruction waits in the queue for the next clearing.
    "gross_first"    : if the seller has the shares AND the buyer has the cash,
                       settle it immediately (model 1 / RTGS); otherwise queue it.
    "gross_only"     : benchmark with no LP at all - queued items are retried
                       one by one in arrival order (FIFO) at each cycle.

  Clearing trigger (whichever comes first, as in the paper)
    * value of instructions that arrived since the last clearing >= value_trigger
    * number of instructions that arrived since the last clearing >= count_trigger
    * minutes since the last clearing >= time_trigger_min
    (Counting only NEW arrivals stops stuck items from firing the trigger forever.)

  Clearing = solve P2 then P3 on the whole queue with current balances; settle
  what the LP picks (partial settlement allowed); the rest stays pending.

  Trust fund: P3 can leave a participant a few rupees overdrawn; the trust lends
  that amount and is repaid automatically from the participant's next inflows.

Measures (paper p.13):
  avg_settle_min : average minutes from arrival to full settlement
                   (trades still pending at the close count until the close)
  cash_used_cr   : sum over participants of the peak amount of their cash line
                   used (borrowed) during the day, in INR crore
  cash_per_100_settled : cash used per INR 100 actually settled (fair when designs
                   settle different amounts)
  global_index   : avg_settle_min x cash_used_cr   (lower is better)
"""
import time
from collections import defaultdict
import numpy as np
import pandas as pd
import config as C
from clearing_lp import solve_clearing


def load_inputs():
    ins = pd.read_csv(C.INSTRUCTIONS_FILE, parse_dates=["timestamp"])
    B = pd.read_csv(C.SEC_BAL_FILE)
    cash = pd.read_csv(C.CASH_BAL_FILE)
    sec0 = {(r.participant, r.ticker): int(r.qty) for r in B.itertuples()}
    cash0 = dict(zip(cash["participant"], cash["cash_inr"].astype(float)))
    return ins, sec0, cash0


class Market:
    def __init__(self, ins, sec0, cash0):
        self.sec = defaultdict(int, sec0)
        self.cash = defaultdict(float, cash0)
        self.cash0 = defaultdict(float, cash0)
        self.min_cash = defaultdict(float, cash0)
        self.owed = defaultdict(float)
        self.trust_peak = 0.0
        self.rem = ins["qty"].to_numpy().copy()
        self.done_at = np.full(len(ins), np.nan)  # minutes after open
        self.s = ins["seller"].to_numpy()
        self.b = ins["buyer"].to_numpy()
        self.k = ins["ticker"].to_numpy()
        self.p = ins["price"].to_numpy()

    def settle(self, l, x, t):
        if x <= 0:
            return
        s, b, k, amt = self.s[l], self.b[l], self.k[l], x * self.p[l]
        self.sec[(s, k)] -= x
        self.sec[(b, k)] += x
        self.cash[b] -= amt
        self.cash[s] += amt
        self.rem[l] -= x
        if self.rem[l] == 0:
            self.done_at[l] = t

    def mark(self, who):
        """Record low points of cash AFTER a settlement event. A clearing batch
        settles all its trades at the same instant, so it is marked once."""
        for i in who:
            self.min_cash[i] = min(self.min_cash[i], self.cash[i])

    def trust(self, who):
        for i in who:
            if self.cash[i] < 0:                       # trust covers the overdraft
                self.owed[i] += -self.cash[i]
                self.cash[i] = 0.0
            if self.owed[i] > 0 and self.cash[i] > 0:  # repay from inflows
                pay = min(self.owed[i], self.cash[i])
                self.owed[i] -= pay
                self.cash[i] -= pay
        self.trust_peak = max(self.trust_peak, sum(self.owed.values()))

    def can_gross(self, l):
        return (self.sec[(self.s[l], self.k[l])] >= self.rem[l]
                and self.cash[self.b[l]] >= self.rem[l] * self.p[l] - 1e-6)


def run(ins, sec0, cash0, rule="all_to_clearing", objective="value",
        value_trigger=np.inf, count_trigger=np.inf, time_trigger_min=np.inf):
    m = Market(ins, sec0, cash0)
    open_ts = ins["timestamp"].iloc[0].normalize() + pd.Timedelta(C.MARKET_OPEN)
    close_min = (pd.Timedelta(C.MARKET_CLOSE) - pd.Timedelta(C.MARKET_OPEN)).total_seconds() / 60
    arr = ((ins["timestamp"] - open_ts).dt.total_seconds() / 60).to_numpy()
    value = ins["value"].to_numpy()

    queue = []
    stats = dict(clearings=0, lp_seconds=0.0, max_queue=0)
    last_clear, new_val, new_cnt = 0.0, 0.0, 0

    def clear(t):
        nonlocal queue, last_clear, new_val, new_cnt
        last_clear, new_val, new_cnt = t, 0.0, 0
        queue = [l for l in queue if m.rem[l] > 0]
        if not queue:
            return
        stats["clearings"] += 1
        stats["max_queue"] = max(stats["max_queue"], len(queue))
        if rule == "gross_only":
            for l in queue:                      # FIFO, one at a time
                if m.can_gross(l):
                    m.settle(l, m.rem[l], t)
                    m.mark([m.b[l]])
        else:
            q = np.array(queue)
            t0 = time.perf_counter()
            x = solve_clearing(list(m.s[q]), list(m.b[q]), list(m.k[q]), m.rem[q], m.p[q],
                               m.sec, m.cash, objective)
            stats["lp_seconds"] += time.perf_counter() - t0
            for l, xl in zip(q, x):
                m.settle(l, int(xl), t)
            who = set(m.s[q]) | set(m.b[q])
            m.mark(who)
            m.trust(who)
        queue = [l for l in queue if m.rem[l] > 0]

    for l in range(len(ins)):
        t = arr[l]
        while last_clear + time_trigger_min <= t:          # timer fired before this arrival
            clear(last_clear + time_trigger_min)
        if rule in ("gross_first", "gross_only") and m.can_gross(l):
            m.settle(l, m.rem[l], t)
            m.mark([m.b[l]])
        else:
            queue.append(l)
            new_val += value[l]
            new_cnt += 1
            if new_val >= value_trigger or new_cnt >= count_trigger:
                clear(t)
    while last_clear + time_trigger_min <= close_min:
        clear(last_clear + time_trigger_min)
    clear(close_min)                                       # final end-of-day cycle

    done = np.where(np.isnan(m.done_at), close_min, m.done_at)
    settled_val = ((ins["qty"].to_numpy() - m.rem) * m.p).sum()
    day_val = value.sum()
    cash_used = sum(m.cash0[i] - m.min_cash[i] for i in m.cash0)
    return dict(
        rule=rule, objective=objective,
        value_trigger_cr=round(value_trigger / 1e7, 2) if np.isfinite(value_trigger) else None,
        count_trigger=count_trigger if np.isfinite(count_trigger) else None,
        time_trigger_min=time_trigger_min if np.isfinite(time_trigger_min) else None,
        avg_settle_min=round(float(np.mean(done - arr)), 2),
        pct_trades_settled=round(100 * np.mean(m.rem == 0), 2),
        pct_value_settled=round(100 * settled_val / day_val, 2),
        cash_used_cr=round(cash_used / 1e7, 2),
        cash_per_100_settled=round(100 * cash_used / max(settled_val, 1), 2),
        trust_peak_pct_of_day=round(100 * m.trust_peak / day_val, 6),
        clearings=stats["clearings"],
        max_queue=stats["max_queue"],
        avg_lp_seconds=round(stats["lp_seconds"] / max(stats["clearings"], 1), 3),
    )
