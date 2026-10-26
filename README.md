# INDEVAL-style settlement on Indian L2 data — step-by-step

This project rebuilds the clearing-and-settlement model from Muñoz et al. (2011),
*INDEVAL Develops a New Operating and Settlement System Using Operations Research*,
using Indian order-book (L2) data. The buyers and sellers are synthetic, because L2
data contains no counterparty identities. 
The dataset used: [Anomaly bias Stock Trades and Order Dataset](https://data.mendeley.com/datasets/fsn6fn7ht8/1)

```
L2 snapshots ──step1──> trades ──step2,3──> DvP instructions (seller, buyer, stock, qty, price, time)
                                                │
                     step4: starting holdings B_ik and cash C_i
                                                │
          step5: RTGS vs LP clearing vs end-of-day      step6: the paper's 48 scenarios
```

---

## Step 0 — Install and test on sample data (10 minutes)

1. Install Python 3.10+ and then the libraries:
   ```
   pip install -r requirements.txt
   ```
2. Run everything on a made-up order book first, so you know the code works:
   ```
   python run_all.py --sample
   ```
   This creates `data/l2_orderbook.csv` (about 10,000 snapshots, 10 NSE stocks) and runs
   steps 1–6. It takes under a minute.

---

## Step 1 — Put your L2 file in and convert it to trades

1. Export your L2 data to CSV with **one row per snapshot**. At minimum it needs:

   | column | meaning |
   |---|---|
   | `timestamp` | date and time of the snapshot |
   | `ticker` | e.g. `RELIANCE` |
   | `bid_px_1`, `bid_sz_1` | best bid price and size |
   | `ask_px_1`, `ask_sz_1` | best ask price and size |
   | `bid_px_2` … `bid_px_5` etc. | deeper levels (optional but better) |
   | `last_px`, `last_sz` | last trade price and size (**optional, strongly recommended**) |
   | `volume` | cumulative traded volume for the day (**optional, strongly recommended**) |

2. Save it as `data/l2_orderbook.csv` (or change `L2_FILE` in `config.py`).
3. If your column names differ, fill in `COLUMN_MAP` in `config.py`, for example
   `"BID_PRICE_1": "bid_px_1"`.
4. Run:
   ```
   python step1_l2_to_trades.py
   ```

**How it detects trades.** For each stock, every snapshot is compared with the one before.
If the best-ask level shrank or disappeared, someone bought (a BUY at that price).
If the best-bid level shrank, someone sold. If the file has `last_px`/`volume`, those
trade prints are used instead, and the side is set by comparing the trade price with
the previous mid-price.

**Why the volume column matters.** On the sample data:

| mode | inferred volume that was real (precision) |
|---|---|
| prints (`last_px`, `volume`) | 100% |
| book diffs + volume check | 100% |
| book diffs only | 55% (cancellations mistaken for trades) |

If you only have book levels, report this as a limitation.

**Big files.** A real NSE day has hundreds of thousands of trades. Set
`AGGREGATE_SECONDS = 60` in `config.py` to merge them into one instruction per stock,
per side, per minute. This keeps each LP small.

Output: `data/trades.csv`

---

## Step 2 — Create the participants

```
python step2_participants.py
```
This creates 30 participants (banks, mutual funds, insurers, brokers, FPIs) with Pareto
activity weights, so a few big players do most of the trading. You can change
`N_PARTICIPANTS`, `PARTICIPANT_TYPES` and `PARETO_ALPHA` in `config.py`. To use real
names (from NSE bulk/block deals or Bloomberg `HDS`), edit `data/participants.csv` by
hand, keep the columns, and skip this step.

Output: `data/participants.csv`

---

## Step 3 — Assign a seller and buyer to every trade

```
python step3_assign_counterparties.py
```
Seller and buyer are drawn at random by activity weight and are always different.
Every participant both buys and sells. This matters: netting only helps when there are
chains such as A→B→C→A.

Each output row is one DvP instruction, which maps to the paper's notation like this:

| paper | column |
|---|---|
| i (seller), j (buyer) | `seller`, `buyer` |
| k (security) | `ticker` |
| l (transaction) | `trade_id` |
| L_ijkl (quantity) | `qty` |
| p_ijkl (price) | `price` |

Output: `data/instructions.csv`

---

## Step 4 — Starting balances

```
python step4_initial_balances.py
```
- **Securities B_ik.** Each participant starts with `SECURITY_COVERAGE` × (what it sells
  of that stock today). The default is 0.3. Below 1.0, some deliveries are only possible
  after the participant receives shares from a purchase. That is the situation where
  batch clearing beats one-at-a-time settlement.
- **Cash C_i.** With `CASH_COVERAGE = None` (the paper's set-up), cash starts at zero and
  borrowing is unlimited. The simulator measures how much each design needs to borrow.
  Set it to, say, 0.15 to run a stress test with limited credit lines.

Outputs: `data/initial_securities.csv`, `data/initial_cash.csv`

---

## Step 5 — Headline comparison

```
python step5_netting_benefit.py
```
**Part A** shows the resources needed to settle every trade, gross versus fully netted.
**Part B** runs the same day three ways with the same balances:

| design (sample data, 30% coverage) | value settled | avg minutes to settle | cash used (₹ cr) |
|---|---|---|---|
| RTGS, one trade at a time (model 1) | 89.9% | 6.7 | 24.9 |
| LP clearing every 5 min (INDEVAL) | 93.5% | 12.6 | 23.5 |
| LP once at end of day (model 3) | 94.1% | 189.4 | 13.4 |

This is the paper's core trade-off. Clearing more often is faster but nets less, so it
needs more liquidity. The LP also settles more value than RTGS with the same holdings,
because it untangles delivery chains that block one-at-a-time settlement.
Your numbers on real data will differ.

Output: `data/step5_comparison.csv`

---

## Step 6 — The paper's 48 scenarios

```
python step6_scenarios.py
```
This runs 2 presettlement rules × 2 objectives × 2 value triggers × 2 count triggers
× 3 time triggers. It then prints the three "best" settings the paper reports
(fastest, least cash, best global index), the average effect of each setting, and a
chart.

| paper | here |
|---|---|
| all DvP to clearing / send directly if funds available | `all_to_clearing` / `gross_first` |
| maximise cash / maximise number of securities | `objective = value` / `quantity` |
| 60,000 / 75,000 million pesos | 1.8% / 2.3% of your day's value, in ₹ |
| 250 / 350 transactions | 1.2% / 1.7% of your day's instruction count (or set `COUNT_TRIGGERS_ABSOLUTE`) |
| 5 / 10 / 15 minutes | same |
| average settlement time, cash used, global index | `avg_settle_min`, `cash_used_cr`, `global_index` |

Outputs: `data/scenario_results.csv`, `data/tradeoff_chart.png`

---

## What is inside the clearing engine (`clearing_lp.py`)

- **P2.** A continuous LP that maximises the settled value (or quantity) subject to
  cash and securities balance constraints, with 0 ≤ x ≤ qty. Partial settlement is
  allowed, as in the paper. Note: the paper prints "X ≤ 0" in P2; it must be X ≥ 0.
- **P3.** An integer rounding step: securities constraints only, with x between
  floor and ceil of the P2 solution. The constraint matrix is a network matrix (totally
  unimodular), so the simplex solution is already integer. If the tight bounds are
  infeasible, the lower bound relaxes to 0.
- **Trust fund.** Dropping cash constraints in P3 can leave tiny overdrafts. A trust
  covers them and is repaid from the next inflows. `trust_peak_pct_of_day` reports its
  size (the paper's was ≤ 0.000032% of the day).
- **Solver.** The paper used CPLEX 10; this uses HiGHS (free, inside scipy). Each
  clearing solves in well under a second, as in the paper.
- **P4** (redemptions and coupons) is not implemented, because equities have no
  redemptions. Add it if you include government bonds.

---



## Limitations

- Counterparties are simulated, not observed.
- With book-only L2 data, cancellations at the best price can be mistaken for trades.
- In India, exchange trades actually settle against the clearing corporation (NSE
  Clearing), not bilaterally. This project asks *what if Indian trades were settled
  through an INDEVAL-style DvP system*.
