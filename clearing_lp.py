# the clearing engine, which is models P2 and P3 from the paper's appendix.
#
# P2 is a continuous LP where partial settlement is allowed:
#     max   sum_l p_l * x_l        (objective="value")
#      or   sum_l x_l              (objective="quantity")
#     s.t.  cash:  sum_{l: buyer=i} p_l x_l - sum_{l: seller=i} p_l x_l <= C_i      for each i
#           secs:  sum_{l: seller=i, sec=k} x_l - sum_{l: buyer=i, sec=k} x_l <= B_ik  for each i,k
#           0 <= x_l <= q_l
# the paper prints "X <= 0" in P2, but that's a typo and it has to be X >= 0.
#
# P3 turns P2's answer into whole shares. it keeps the securities rows, drops the cash rows,
# and keeps each x_l between floor and ceil of P2's value. each x shows up as +1 for the
# seller and -1 for the buyer, so the matrix is a network matrix, which is totally
# unimodular, and simplex hands back integers on its own (that's the paper's "unimodular"
# point). if those tight bounds turn out infeasible we drop the lower bound to 0, which
# always works. dropping the cash rows can leave tiny overdrafts, and the trust fund in
# simulator.py covers those, same as in the paper.
#
# the paper used CPLEX 10, we use the free HiGHS solver that comes with scipy.
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix


def _sec_rows(seller, buyer, ticker, sec_bal):
    # one securities row for every (participant, ticker) pair that sells something
    keys = sorted(set(zip(seller, ticker)))
    idx = {k: r for r, k in enumerate(keys)}
    rows, cols, vals = [], [], []
    for l, (s, b, k) in enumerate(zip(seller, buyer, ticker)):
        rows.append(idx[(s, k)]); cols.append(l); vals.append(1.0)
        if (b, k) in idx:
            rows.append(idx[(b, k)]); cols.append(l); vals.append(-1.0)
    rhs = np.array([sec_bal.get(k, 0) for k in keys], dtype=float)
    return rows, cols, vals, rhs, len(keys)


def solve_clearing(seller, buyer, ticker, qty, price, sec_bal, cash_bal, objective="value"):
    # seller, buyer, ticker, qty and price have one entry per queued instruction, where qty
    # is what's still left to settle. sec_bal[(i, k)] is how many shares of k member i has
    # right now and cash_bal[i] is the cash it can still use. we return an integer array
    # saying how many shares of each instruction to settle.
    n = len(qty)
    if n == 0:
        return np.zeros(0, dtype=int)
    qty = np.asarray(qty, dtype=float)
    price = np.asarray(price, dtype=float)
    c = -(price if objective == "value" else np.ones(n))

    # P2, with securities and cash rows
    r, cc, v, sec_rhs, n_sec = _sec_rows(seller, buyer, ticker, sec_bal)
    # cash rows only for members whose cash is actually limited, anything >= 1e14 counts as unlimited
    parts = sorted(p for p in set(seller) | set(buyer) if cash_bal.get(p, 0.0) < 1e14)
    pidx = {p: n_sec + j for j, p in enumerate(parts)}
    for l in range(n):
        if buyer[l] in pidx:
            r.append(pidx[buyer[l]]); cc.append(l); v.append(price[l])
        if seller[l] in pidx:
            r.append(pidx[seller[l]]); cc.append(l); v.append(-price[l])
    A = coo_matrix((v, (r, cc)), shape=(n_sec + len(parts), n)).tocsr()
    b = np.concatenate([sec_rhs, [max(cash_bal.get(p, 0.0), 0.0) for p in parts]])
    res = linprog(c, A_ub=A, b_ub=b, bounds=np.column_stack([np.zeros(n), qty]), method="highs")
    x2 = res.x if res.status == 0 else np.zeros(n)

    # P3, securities rows only, with x between floor and ceil of P2
    r, cc, v, sec_rhs, n_sec = _sec_rows(seller, buyer, ticker, sec_bal)
    A3 = coo_matrix((v, (r, cc)), shape=(n_sec, n)).tocsr()
    lo, hi = np.floor(x2 + 1e-7), np.minimum(np.ceil(x2 - 1e-7), qty)
    for lower in (lo, np.zeros(n)):
        res3 = linprog(c, A_ub=A3, b_ub=sec_rhs, bounds=np.column_stack([lower, hi]),
                       method="highs-ds")
        if res3.status == 0:
            x = np.round(res3.x).astype(int)
            if (A3 @ x <= sec_rhs + 1e-6).all():
                return x
    return np.zeros(n, dtype=int)
