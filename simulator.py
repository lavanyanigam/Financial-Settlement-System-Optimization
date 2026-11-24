# the settlement simulator, following the paper's figure 1: presettlement, then clearing,
# then settlement. instructions come in one at a time in time order. like the paper, we
# replay one real busy day instead of making up random arrivals.
#
# presettlement rules
#   "all_to_clearing"  every instruction waits in the queue for the next clearing.
#   "gross_first"      if the seller has the shares and the buyer has the cash, settle it
#                      right away (model 1 / RTGS), otherwise queue it.
#   "gross_only"       our benchmark with no LP at all, queued items just get retried one
#                      by one in arrival order at each cycle.
#
# a clearing fires on whichever trigger is hit first, same as the paper: the value of new
# arrivals since the last clearing, the number of new arrivals, or the minutes since the
# last clearing. we only count new arrivals, otherwise stuck items would keep firing it.
# a clearing solves P2 and P3 on the whole queue with the current balances, settles what
# the LP picks (partial settlement is fine) and leaves the rest pending.
#
# P3 can leave a member a few rupees overdrawn, so a trust fund lends that and gets paid
# back automatically from the member's next inflows.
#
# what we measure (paper p. 13)
#   avg_settle_min        average minutes from arrival to fully settled, and anything still
#                         pending at the close counts up to the close
#   cash_used_cr          sum over members of the most each one had to borrow, in crore
#   cash_per_100_settled  cash used per Rs 100 actually settled, which is fairer when designs
#                         settle different amounts
#   global_index          avg_settle_min x cash_used_cr, lower is better
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
        self.done_at = np.full(len(ins), np.nan)  # minutes after the open
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
        # note each member's lowest cash after a settlement. a clearing batch settles
        # everything at the same instant, so it only gets marked once.
        for i in who:
            self.min_cash[i] = min(self.min_cash[i], self.cash[i])

    def trust(self, who):
        for i in who:
            if self.cash[i] < 0:                       # the trust covers the overdraft
                self.owed[i] += -self.cash[i]
                self.cash[i] = 0.0
            if self.owed[i] > 0 and self.cash[i] > 0:  # and gets paid back from inflows
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
            for l in queue:                      # first in first out, one at a time
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
        while last_clear + time_trigger_min <= t:          # the timer went off before this arrival
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
    clear(close_min)                                       # one last clearing at the close

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
