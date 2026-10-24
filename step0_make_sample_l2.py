"""
STEP 0 (optional) - make a SAMPLE L2 order-book file so you can test the
whole pipeline before your real data is ready.

It simulates a limit order book for 10 NSE stocks over one trading day and
writes one snapshot row after every book event (trade, cancel, new order).
It also writes the TRUE list of trades, so step 1 can tell you how accurate
the trade inference is.

Run:  python step0_make_sample_l2.py
Out:  data/l2_orderbook.csv, data/sample_true_trades.csv
"""
import os
import numpy as np
import pandas as pd
import config as C

rng = np.random.default_rng(C.SEED)
TICK = 0.05
LEVELS = C.BOOK_LEVELS
DAY = "2026-10-08"   # a Thursday (weekly expiry day = busy)

STOCKS = {           # ticker: (start price, events per day)
    "RELIANCE": (2850, 1400), "HDFCBANK": (1650, 1300), "ICICIBANK": (1250, 1100),
    "INFY": (1850, 1000), "TCS": (4100, 800), "SBIN": (820, 1200),
    "ITC": (470, 900), "LT": (3600, 600), "AXISBANK": (1150, 800), "BHARTIARTL": (1700, 700),
}


def rnd_size():
    return int(max(1, rng.lognormal(mean=5.0, sigma=0.9)))        # median ~150 shares


def new_book(p0):
    bb = round(p0 / TICK) * TICK
    bids = [[round(bb - i * TICK, 2), rng.integers(200, 3000)] for i in range(LEVELS)]
    asks = [[round(bb + (i + 1) * TICK, 2), rng.integers(200, 3000)] for i in range(LEVELS)]
    return bids, asks


def refill(levels, side):
    """Keep exactly LEVELS levels: append a deeper level when one disappears."""
    levels[:] = [l for l in levels if l[1] > 0]
    while len(levels) < LEVELS:
        if levels:
            last = levels[-1][0]
            px = last - TICK if side == "bid" else last + TICK
        else:
            px = 100.0
        levels.append([round(px, 2), int(rng.integers(200, 3000))])


def snapshot(t, tic, bids, asks, last_px, last_sz, vol):
    row = {"timestamp": t, "ticker": tic}
    for n in range(LEVELS):
        row[f"bid_px_{n+1}"], row[f"bid_sz_{n+1}"] = bids[n]
        row[f"ask_px_{n+1}"], row[f"ask_sz_{n+1}"] = asks[n]
    row.update(last_px=last_px, last_sz=last_sz, volume=vol)
    return row


rows, true_trades = [], []
open_ts = pd.Timestamp(f"{DAY} {C.MARKET_OPEN}")
day_secs = (pd.Timestamp(f"{DAY} {C.MARKET_CLOSE}") - open_ts).total_seconds()

for tic, (p0, n_events) in STOCKS.items():
    bids, asks = new_book(p0)
    last_px, last_sz, vol = np.nan, 0, 0
    # busier at open and close (U-shaped intraday pattern)
    u = rng.beta(0.7, 0.7, size=n_events)
    times = np.sort(u * day_secs)
    rows.append(snapshot(open_ts, tic, bids, asks, last_px, last_sz, vol))
    for s in times:
        t = open_ts + pd.Timedelta(seconds=float(s))
        ev = rng.random()
        if ev < 0.55:                               # market order -> trade(s)
            side = "buy" if rng.random() < 0.5 else "sell"
            book = asks if side == "buy" else bids
            left = rnd_size()
            while left > 0:
                px, sz = book[0]
                fill = min(left, sz)
                book[0][1] -= fill
                left -= fill
                true_trades.append(dict(timestamp=t, ticker=tic, side=side, price=px, qty=fill))
                last_px, last_sz, vol = px, fill, vol + fill
                refill(book, "ask" if side == "buy" else "bid")
        elif ev < 0.85:                             # cancellation at best
            book = bids if rng.random() < 0.5 else asks
            book[0][1] = int(book[0][1] * rng.uniform(0, 0.9))
            refill(book, "bid" if book is bids else "ask")
        else:                                       # new limit order
            if rng.random() < 0.5:
                spread = round(asks[0][0] - bids[0][0], 2)
                if spread > TICK + 1e-9:            # improve inside the spread
                    bids.insert(0, [round(bids[0][0] + TICK, 2), rnd_size()]); bids.pop()
                else:
                    bids[0][1] += rnd_size()
            else:
                spread = round(asks[0][0] - bids[0][0], 2)
                if spread > TICK + 1e-9:
                    asks.insert(0, [round(asks[0][0] - TICK, 2), rnd_size()]); asks.pop()
                else:
                    asks[0][1] += rnd_size()
        rows.append(snapshot(t, tic, bids, asks, last_px, last_sz, vol))

os.makedirs(C.DATA_DIR, exist_ok=True)
l2 = pd.DataFrame(rows).sort_values(["timestamp", "ticker"], kind="stable")
l2.to_csv(C.L2_FILE, index=False)
pd.DataFrame(true_trades).to_csv("data/sample_true_trades.csv", index=False)
print(f"Wrote {len(l2):,} L2 snapshots for {len(STOCKS)} stocks -> {C.L2_FILE}")
print(f"True trades (for checking step 1): {len(true_trades):,} -> data/sample_true_trades.csv")
