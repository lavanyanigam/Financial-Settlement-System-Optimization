"""
STEP 1 - turn L2 order-book snapshots into a list of trades.

How a trade is detected (per ticker, comparing each snapshot with the one before):
  * BUY  (someone hit the ask): best-ask levels below the new best ask vanished,
         or the size at the same best-ask price shrank.
  * SELL (someone hit the bid): same thing on the bid side.
  * If your file has last_px / last_sz / volume columns, those trade prints are
    used instead (much more reliable), and the side is set with the quote rule
    (trade above the previous mid = buy, below = sell, tie -> tick rule).

Limitation to state in your report: with book diffs only, a cancellation at the
best price looks exactly like a trade. A cumulative volume column fixes this.

Run:  python step1_l2_to_trades.py
Out:  data/trades.csv  (trade_id, timestamp, ticker, side, price, qty, value)
"""
import os
import numpy as np
import pandas as pd
import config as C

EPS = 1e-6


def load_l2():
    df = pd.read_csv(C.L2_FILE)
    df = df.rename(columns=C.COLUMN_MAP)
    need = ["timestamp", "ticker", "bid_px_1", "bid_sz_1", "ask_px_1", "ask_sz_1"]
    missing = [c for c in need if c not in df.columns]
    if missing:
        raise SystemExit(f"Your L2 file is missing {missing}. Fix COLUMN_MAP in config.py.")
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df.sort_values(["ticker", "timestamp"], kind="stable").reset_index(drop=True)


def levels(row, side, n_levels):
    out = []
    for n in range(1, n_levels + 1):
        px, sz = row.get(f"{side}_px_{n}"), row.get(f"{side}_sz_{n}")
        if px is None or sz is None or pd.isna(px) or pd.isna(sz):
            break
        out.append((float(px), float(sz)))
    return out


def consumed(prev_lv, cur_lv, side):
    """Shares taken out of the top of one side of the book between two snapshots."""
    if not prev_lv or not cur_lv:
        return []
    cur_best_px, cur_best_sz = cur_lv[0]
    fills = []
    for px, sz in prev_lv:
        deeper_than_new_best = px < cur_best_px - EPS if side == "ask" else px > cur_best_px + EPS
        if deeper_than_new_best:            # whole level disappeared
            fills.append((px, sz))
        elif abs(px - cur_best_px) < EPS:   # same best price, smaller size
            if cur_best_sz < sz - EPS:
                fills.append((px, sz - cur_best_sz))
            break
        else:                               # new best is better than old one -> no trade
            break
    return fills


def infer_ticker(g, mode, n_levels):
    rows = g.to_dict("records")
    has_vol = "volume" in g.columns
    trades = []
    last_trade_px = np.nan
    for prev, cur in zip(rows[:-1], rows[1:]):
        t, tic = cur["timestamp"], cur["ticker"]
        dv = (cur["volume"] - prev["volume"]) if has_vol else None

        if mode == "prints":
            qty = dv if has_vol else (cur["last_sz"] if cur["last_px"] != prev["last_px"]
                                      or cur["last_sz"] != prev["last_sz"] else 0)
            if qty and qty > 0 and not pd.isna(cur["last_px"]):
                px = float(cur["last_px"])
                mid = (prev["bid_px_1"] + prev["ask_px_1"]) / 2
                if px > mid + EPS:
                    side = "buy"
                elif px < mid - EPS:
                    side = "sell"
                else:   # tick rule
                    side = "buy" if (np.isnan(last_trade_px) or px >= last_trade_px) else "sell"
                trades.append((t, tic, side, px, float(qty)))
                last_trade_px = px
            continue

        # book-diff modes
        buys = consumed(levels(prev, "ask", n_levels), levels(cur, "ask", n_levels), "ask")
        sells = consumed(levels(prev, "bid", n_levels), levels(cur, "bid", n_levels), "bid")
        if mode == "book_volume" and has_vol and dv <= 0:
            continue    # book shrank but nothing traded -> it was a cancellation
        for px, q in buys:
            trades.append((t, tic, "buy", px, q))
        for px, q in sells:
            trades.append((t, tic, "sell", px, q))
    return trades


def check_against_truth(tr):
    truth_file = "data/sample_true_trades.csv"
    if not os.path.exists(truth_file) or C.L2_FILE != "data/l2_orderbook.csv":
        return
    truth = pd.read_csv(truth_file, parse_dates=["timestamp"])
    key = ["timestamp", "ticker", "side"]
    a = tr.groupby(key)["qty"].sum().rename("inferred")
    b = truth.groupby(key)["qty"].sum().rename("true")
    m = pd.concat([a, b], axis=1).fillna(0)
    matched = np.minimum(m["inferred"], m["true"]).sum()
    print("\nAccuracy vs the sample's true trades (only possible with sample data):")
    print(f"  true volume      : {m['true'].sum():>12,.0f} shares")
    print(f"  inferred volume  : {m['inferred'].sum():>12,.0f} shares")
    print(f"  precision        : {matched / m['inferred'].sum():.1%}  (inferred volume that was real)")
    print(f"  recall           : {matched / m['true'].sum():.1%}  (real volume that was found)")


def main():
    df = load_l2()
    has_prints = {"last_px", "last_sz"}.issubset(df.columns)
    has_vol = "volume" in df.columns
    mode = C.INFERENCE_MODE
    if mode == "auto":
        mode = "prints" if has_prints else ("book_volume" if has_vol else "book_only")
    n_levels = max(int(c.split("_")[-1]) for c in df.columns if c.startswith("ask_px_"))
    n_levels = min(n_levels, C.BOOK_LEVELS) if C.BOOK_LEVELS else n_levels
    print(f"Read {len(df):,} snapshots, {df['ticker'].nunique()} tickers, {n_levels} levels. Mode: {mode}")

    trades = []
    for _, g in df.groupby("ticker", sort=False):
        trades += infer_ticker(g, mode, n_levels)
    tr = pd.DataFrame(trades, columns=["timestamp", "ticker", "side", "price", "qty"])
    tr = tr[tr["qty"] > 0]
    check_against_truth(tr)

    if C.AGGREGATE_SECONDS:
        tr["bucket"] = tr["timestamp"].dt.floor(f"{C.AGGREGATE_SECONDS}s")
        tr["pv"] = tr["price"] * tr["qty"]
        tr = (tr.groupby(["bucket", "ticker", "side"])
                .agg(timestamp=("timestamp", "max"), qty=("qty", "sum"), pv=("pv", "sum"))
                .reset_index())
        tr["price"] = tr["pv"] / tr["qty"]
        tr = tr.drop(columns=["bucket", "pv"])
        print(f"Aggregated into {C.AGGREGATE_SECONDS}s buckets.")

    tr["qty"] = tr["qty"].round().astype(int)
    tr = tr[tr["qty"] > 0].sort_values("timestamp", kind="stable").reset_index(drop=True)
    tr["price"] = tr["price"].round(2)
    tr["value"] = tr["price"] * tr["qty"]
    tr.insert(0, "trade_id", np.arange(1, len(tr) + 1))
    tr.to_csv(C.TRADES_FILE, index=False)

    print(f"\nWrote {len(tr):,} trades -> {C.TRADES_FILE}")
    print(f"Day value: INR {tr['value'].sum() / 1e7:,.1f} crore")
    print(tr.groupby("ticker")["value"].agg(["count", "sum"])
            .rename(columns={"count": "trades", "sum": "value_inr"})
            .sort_values("value_inr", ascending=False).to_string())


if __name__ == "__main__":
    main()
