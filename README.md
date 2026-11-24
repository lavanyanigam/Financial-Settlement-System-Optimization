# INDEVAL-style settlement on Indian exchange trades

This project rebuilds the clearing-and-settlement engine from Muñoz et al. (2011),
*INDEVAL Develops a New Operating and Settlement System Using Operations Research*
(Interfaces 41(1), 8–17), and runs it on one real day of Indian exchange trades.

It is a **what-if**: Indian exchange trades actually settle through a clearing
corporation on T+1. We ask how much liquidity an INDEVAL-style DvP engine would need
for the same trades, and how long trades would wait.

---

## 1. Data

**Source:** *Anomaly bias Stock Trades and Order Dataset* — Ahtas, Kadam, Barshikar,
Shitole, Ghadge (2025), Mendeley Data, V1, doi:10.17632/fsn6fn7ht8.1, licence CC BY 4.0.
Link: <https://data.mendeley.com/datasets/fsn6fn7ht8/1>

It contains trade and order logs from an Indian exchange's trading system for 7 days in
2007, in `data/Stock_Trades_Orders/`:

| file | rows | used? |
|---|---|---|
| `Trades .csv` | 414,957 matched trades | **yes** — every trade has a buy and a sell member code |
| `Orders .csv` | 602,473 orders | no (the settlement model only needs executed trades) |

**Why this dataset.** The LP needs, for every trade, *who sold to whom*. Public L1/L2
order-book data never shows counterparties; Level 3 / order-and-trade data does, but is
expensive (NSE Cash Market Level 3: ₹38–42.5 lakh a year; NSE historical order and trade
data for students: ₹6.25 lakh a year; a Bloomberg Terminal seat: about US$32,000 a year).
This open dataset has anonymised member codes on both sides of every trade.

Every file in `data/` is built from `Trades .csv` by the scripts below; nothing in the
pipeline is generated or made up, the only assumptions are the opening balances and
trigger sizes listed next.

### What is real and what is assumed

| input (paper notation) | where it comes from | real or assumed |
|---|---|---|
| seller i, buyer j | `SELL_MEMBER_CODE`, `BUY_MEMBER_CODE` (533 brokers) | **real** (anonymised) |
| security k | `SCRIP_CODE` (4 scrips) | **real** |
| quantity L, price p | `TRADE_QUANTITY`, `TRADE_RATE` (paise → ₹) | **real** |
| order of arrival | `TRADE_SEQUENCE` | **real** |
| clock time | `TRADE_TIME` holds only mm:ss; the hour is rebuilt (below) | **real, reconstructed** |
| securities B_ik | 30% of what member i sells of k that day (`SECURITY_COVERAGE`) | assumed |
| cash C_i | start at ₹0 with unlimited credit; we measure peak borrowing (`CASH_COVERAGE = None`) | assumed |
| clearing triggers | same shares of our day as the paper's (see section 4) | assumed scaling |

**Participants are broker members**, not end clients (the file also has 61,878 client
IDs). Brokers are the ones that settle with a depository, like INDEVAL's participants.

### Rebuilding the trade time

`TRADE_TIME` was exported as `mm:ss.s`, so the hour is missing. Walking through the
trades in `TRADE_SEQUENCE` order, the minute counter wraps back to 00 at each new hour;
`prep.py` adds an hour at every backward jump of more than 30 minutes (and takes it back
off on a forward jump of more than 30 minutes, which happens when trades from different
scrips straddle the hour). The session opened at 09:55.

Check: within each scrip, the rebuilt times never go backwards in `TRADE_NUMBER` order
(0 violations on every one of the 7 days; every day runs 09:55 to about 16:00). The day
is far from uniform — 8,306 instructions in the 9 o'clock hour, 76,336 in the 2 o'clock
hour — so this matters for waiting times and for when the clearing triggers fire.

### The day we replay

13 April 2007, the busiest day in the file: 243,139 trades → minus 120 after the 15:30
close → minus 2,497 where the same broker is on both sides = **240,522 DvP instructions**,
533 brokers, 4 scrips, **₹862.5 crore**. One scrip (556155) is 97% of the trades and 99%
of the value.

---

## 2. Pipeline

```
data/Stock_Trades_Orders/Trades .csv     (raw exchange trade log)
              │
           prep.py            clean, pick the day, rebuild the hour, drop self-trades
              │
   ┌──────────┴──────────┐
data/instructions.csv   data/participants.csv
              │
  step4_initial_balances.py   → data/initial_securities.csv (B_ik), data/initial_cash.csv (C_i)
              │
   ┌──────────┴───────────────────────┐
step5_netting_benefit.py          step6_scenarios.py
RTGS vs LP every 5 min vs          the paper's 48 scenarios
LP once at end of day              → data/scenario_results.csv
→ data/step5_comparison.csv        → data/tradeoff_chart.png
   └──────────┬───────────────────────┘
      simulator.py  ⇄  clearing_lp.py
      (paper Fig. 1)    (models P2 + P3, HiGHS solver)
```

| file | what it does |
|---|---|
| `config.py` | every setting: files, market hours, coverage, the 48-scenario grid |
| `prep.py` | raw trades → `instructions.csv`, `participants.csv` (member code, share of traded value) |
| `step4_initial_balances.py` | opening securities B_ik and cash C_i |
| `clearing_lp.py` | models P2 and P3 |
| `simulator.py` | replays the day: presettlement → queue → clearing → settlement, plus trust fund |
| `step5_netting_benefit.py` | headline comparison of three settlement designs |
| `step6_scenarios.py` | the paper's 48-scenario experiment and the trade-off chart |
| `run_all.py` | runs prep → step4 → step5 → step6 |

---

## 3. How to run

```bash
pip install -r requirements.txt
python run_all.py          # about a minute on a laptop
```

or step by step: `python prep.py`, `python step4_initial_balances.py`,
`python step5_netting_benefit.py`, `python step6_scenarios.py`.

To replay another day, set `DATE` at the top of `prep.py` (e.g. `"19-Jul-07"`).
To stress-test with limited credit, set `CASH_COVERAGE = 0.15` in `config.py`.

---

## 4. The model, and how it maps to the paper

### P2 — continuous LP (one clearing cycle)
$$\max \sum_l p_l x_l \quad\text{(cash value)} \qquad\text{or}\qquad \max \sum_l x_l \quad\text{(shares)}$$
subject to, for every member i and security k:
$$\sum_{l:\,\text{buyer}=i} p_l x_l - \sum_{l:\,\text{seller}=i} p_l x_l \le C_i \qquad\text{(cash)}$$
$$\sum_{l:\,\text{seller}=i,\,k} x_l - \sum_{l:\,\text{buyer}=i,\,k} x_l \le B_{ik} \qquad\text{(securities)}$$
$$0 \le x_l \le \text{remaining quantity of } l \qquad\text{(partial settlement allowed)}$$
The paper prints "X ≤ 0" in P2; it must be X ≥ 0.

### P3 — integer repair
Securities rows only, no cash rows, with ⌊x\*⌋ ≤ x ≤ ⌈x\*⌉ from P2. Each variable appears
+1 for the seller and −1 for the buyer, a network matrix, which is totally unimodular, so
the simplex solution is already integer (the paper's "unimodular" argument). If those
bounds are infeasible, the lower bound relaxes to 0. Dropping the cash rows can leave
tiny overdrafts; a trust fund lends them and is repaid from the next inflows.

**Not implemented:** P1 (superseded by P2) and P4 (redemptions and coupons — equities
have none). Solver: HiGHS inside SciPy; the paper used CPLEX 10.

**Note on cash.** With `CASH_COVERAGE = None` every member has unlimited credit, so
`clearing_lp.py` leaves out the cash rows (the cash constraint can never bind). The LP then
only enforces securities, and liquidity is measured as each member's peak borrowing.
Run with `CASH_COVERAGE = 0.15` to make the cash constraint active.

### The paper's settings → ours

| paper | here |
|---|---|
| all DvP to clearing / send directly if funds are available | `all_to_clearing` / `gross_first` |
| maximise cash / maximise number of securities | `objective = value` / `quantity` |
| value trigger 60,000 / 75,000 million pesos | 1.8% / 2.3% of our day's value = ₹15.52 / ₹19.84 crore |
| count trigger 250 / 350 instructions | 1.2% / 1.7% of our day's instructions = 2,886 / 4,089 — **our choice** (keeps the 250:350 ratio; the paper gives no daily count) |
| time trigger 5 / 10 / 15 min | same |
| average settlement time, money required, global index | `avg_settle_min`, `cash_used_cr` (sum of peak borrowing), `global_index` = time × cash |

Benchmark not in the 48 grid: `gross_only` = model 1 / RTGS, one trade at a time,
queued trades retried in arrival order every minute, no LP.

---

## 5. Results (13 April 2007, 30% securities coverage, unlimited credit)

### Step 5 — three designs, same balances

| design | trades settled | value settled | avg wait (min) | cash used (₹ cr) | clearings | avg LP solve |
|---|---|---|---|---|---|---|
| RTGS, one at a time (model 1) | 99.40% | 98.68% | 1.07 | 76.98 | 336 | — |
| **LP clearing every 5 min (INDEVAL)** | 99.10% | 98.72% | 4.19 | **64.01** | 68 | 0.021 s |
| LP once at end of day (model 3) | 99.13% | 98.81% | 138.09 | 24.91 | 1 | 1.67 s |

- 5-minute LP clearing needs **17% less cash** than RTGS for about 3 more minutes of waiting.
- End-of-day netting needs **68% less cash**, but trades wait 2.3 hours on average.
- With the same holdings, the LP designs settle slightly more value: they untangle
  delivery chains (A→B→C→A) that block one-at-a-time settlement.
- The trust fund was never needed.

Resources needed to settle every trade (Part A): cash ₹82.5 cr if each trade settles on
arrival vs ₹27.6 cr fully netted (67% less); shares 1.45 M vs 0.57 M (61% less).

### Step 6 — the 48 scenarios

- Two clusters, set by the presettlement rule: **gross first** 1.40–1.58 min and
  ₹77.1–77.4 cr; **all to clearing** 3.01–4.42 min and ₹67.0–70.9 cr.
- **Fastest and best global index:** gross first, max cash value, ₹15.52 cr, 2,886
  instructions, 15 min → 1.40 min, ₹77.36 cr, GPI 108.3.
- **Least cash:** all to clearing, max shares, ₹15.52 cr, 4,089 instructions, 15 min →
  4.42 min, ₹67.04 cr.
- Average effect of each setting (mean over the other 24 runs):

| setting | levels | avg wait (min) | cash used (₹ cr) |
|---|---|---|---|
| presettlement | all to clearing / gross first | 3.64 / 1.47 | 69.01 / 77.20 |
| objective | max cash value / max shares | 2.49 / 2.63 | 73.17 / 73.04 |
| value trigger | ₹15.52 / ₹19.84 cr | 2.56 / 2.56 | 73.07 / 73.14 |
| count trigger | 2,886 / 4,089 | 2.45 / 2.67 | 73.62 / 72.58 |
| time trigger | 5 / 10 / 15 min | 2.36 / 2.61 / 2.71 | 73.41 / 73.15 / 72.75 |

As in the paper, the settings that are fastest are the opposite of the ones that use the
least cash. Unlike the paper (best GPI: all to clearing, 5 min), our best GPI uses gross
first: with unlimited credit gross settlement is never blocked by cash, so its extra
~₹8 cr of borrowing is small next to the ~2 minutes it saves.

---

## 6. Limitations

- Counterparties are broker member codes, not end clients.
- One day, four scrips, one of which is 99% of the value.
- Clock hours are reconstructed (validated, but not given in the file).
- Opening holdings (30%) and unlimited credit are assumptions, not observed balances.
- Indian trades really settle through a central counterparty on T+1; this is a what-if.
- P3 is a rounding repair, not a global optimum (as in the paper); P4 is not implemented.
- A deterministic replay of one day: no random arrivals, no confidence intervals.
- The dataset was published for anomaly/fraud detection research; we use it as-is.
