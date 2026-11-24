# INDEVAL Settlement Optimization on Indian Equity Market Data

This project replicates and evaluates the Central Securities Depository clearing-and-settlement optimization model from Muñoz et al. (2011), *INDEVAL Develops a New Operating and Settlement System Using Operations Research*, Interfaces 41(1), 8–17 (Franz Edelman Award, INFORMS), using **real Indian stock exchange trade data**.
The dataset used: [Anomaly bias Stock Trades and Order Dataset](https://data.mendeley.com/datasets/fsn6fn7ht8/1)

---

## 1. What This Project Does

In securities settlement, **Delivery versus Payment (DvP)** requires that the transfer of shares occurs if and only if the corresponding payment is completed.

Traditional systems face an operational trade-off:
* **Model 1 / RTGS (Real-Time Gross Settlement):** Trades settle one-by-one in real time. Settlement is fast, but requires large cash and share inventories, and trades can get stuck waiting on each other (intraday gridlock).
* **Model 3 (End-of-Day Net Settlement):** Trades accumulate all day and are netted out at market close. Very liquidity-efficient, but settlement is delayed until end of day, leaving significant intraday risk.

**The INDEVAL Innovation ("Dalí"):**
A **continuous hybrid settlement engine** that runs periodic batches (e.g., every 5, 10, or 15 minutes) throughout the day using **Linear Programming (LP)**. The LP untangles circular delivery chains ($A \to B \to C \to A$) and unlocks frozen queues with minimal cash.

This repository implements the paper's clearing models P2 and P3 inside a full presettlement → clearing → settlement simulator, and tests it on **240,522 real exchange trades** between **533 broker members** on the Indian stock market. (P1 is superseded by P2; P4 adds redemptions, which equities do not have.)

It is a **what-if**: Indian exchange trades actually settle through a clearing corporation on T+1. We ask how much liquidity an INDEVAL-style DvP engine would need for the same trades, and how long trades would wait.

---

## 2. Dataset Information

**Source:** *Anomaly bias Stock Trades and Order Dataset*, Ahtas, Kadam, Barshikar, Shitole, Ghadge (2025), Mendeley Data, V1, doi:10.17632/fsn6fn7ht8.1, licence CC BY 4.0.

The data comes from historical Indian stock exchange trade logs covering 7 trading days in 2007 (`data/Stock_Trades_Orders/Trades .csv`; `Orders .csv` is included but not needed). We replay the busiest day by value, **13 April 2007**:
* **Trades:** Real matched transactions with quantities, prices in paise (converted to ₹ INR), and exchange sequence numbers. 243,139 trades that day, minus 120 after the 15:30 close and 2,497 where the same broker is on both sides = **240,522 DvP instructions** worth **₹862.5 crore**.
* **Securities:** 4 scrip codes as given in the dataset (e.g., `555835`, `556155`). Scrip `556155` alone is 97% of the trades and 99% of the value.
* **Participants:** Anonymised exchange broker members (`BUY_MEMBER_CODE` and `SELL_MEMBER_CODE`, prefixed as `M<id>`).
* **Session Replay:** `TRADE_TIME` only holds mm:ss, so `prep.py` rebuilds the hour by walking the trades in `TRADE_SEQUENCE` order and adding an hour each time the minutes wrap back to 00 (checked: within each scrip the rebuilt times never go backwards). The day is replayed from 09:55 AM to 03:30 PM.

**Assumptions** (the dataset has no account balances): each member starts with 30% of the shares it sells of each stock that day ($B_{ik}$), and with ₹0 cash and unlimited credit ($C_i$), so the simulator measures each member's peak borrowing. Both are set in `config.py` (`SECURITY_COVERAGE`, `CASH_COVERAGE`).

---

## 3. Pipeline & Architecture

```
[data/Stock_Trades_Orders/Trades .csv]  (Real Indian exchange trade log)
                   │
                prep.py
                   │
       ┌───────────┴───────────────────────┐
       ▼                                   ▼
[data/instructions.csv]         [data/participants.csv]
(240,522 DvP instructions)      (533 broker members)
       │
step4_initial_balances.py
       │
       ├──> [data/initial_securities.csv] (Starting stock holdings B_ik: 30% coverage)
       └──> [data/initial_cash.csv]       (Starting cash C_i: zero with unlimited credit by default)
       │
 ┌─────┴────────────────────────────────────────────────┐
 │                                                      │
step5_netting_benefit.py                       step6_scenarios.py
• Gross vs Net comparison                      • 48-Scenario Simulation Grid
• RTGS vs 5-min LP vs EOD Netting              • Speed vs Liquidity Trade-off Chart
 │                                                      │
 └──────────────────────────┬───────────────────────────┘
                            ▼
              simulator.py <──> clearing_lp.py
              (Event Engine)     (HiGHS LP Solver: P2 + P3)
```

---

## 4. Quick Start

### Installation
Python 3.10+ is recommended. Activate your virtual environment and install requirements:
```bash
pip install -r requirements.txt
```

### Run the Complete Pipeline
To execute data cleaning, balance generation, headline comparisons, and the 48-scenario grid in one command (about a minute on a laptop):
```bash
python run_all.py
```

Or run individual steps manually:
1. **Prepare trade instructions & participants:**
   ```bash
   python prep.py
   ```
2. **Set starting inventories ($B_{ik}$) and cash limits ($C_i$):**
   ```bash
   python step4_initial_balances.py
   ```
3. **Run headline comparison (RTGS vs INDEVAL LP vs End-of-Day):**
   ```bash
   python step5_netting_benefit.py
   ```
4. **Run the 48-scenario simulation experiment:**
   ```bash
   python step6_scenarios.py
   ```

To replay another day, set `DATE` at the top of `prep.py` (e.g. `"19-Jul-07"`). To stress-test with limited credit, set `CASH_COVERAGE = 0.15` in `config.py`.

---

## 5. File Descriptions

* **`config.py`**: Central parameter file (file paths, market hours, security and cash coverage, trigger thresholds, scenario grid).
* **`prep.py`**: Ingests raw exchange trades, converts paise to rupees, picks the busiest day, rebuilds the clock hour, drops trades after the close and internal broker crosses (same broker on both sides), and generates `instructions.csv` and `participants.csv`.
* **`clearing_lp.py`**: Implements **Model P2** (continuous LP maximizing settled value or volume) and **Model P3** (totally unimodular integer rounding). Solves via SciPy's `HiGHS` solver.
* **`simulator.py`**: Event-driven settlement simulator implementing Figure 1 from the paper (presettlement rules, batch queues, triggering conditions, and trust fund overdraft tracking).
* **`step4_initial_balances.py`**: Sets initial security inventories ($B_{ik} = 30\%$ of daily sales) to simulate inventory friction, and initializes cash accounts ($C_i$).
* **`step5_netting_benefit.py`**: Computes gross vs. net liquidity requirements and compares RTGS, INDEVAL 5-minute LP clearing, and End-of-Day netting under identical initial conditions.
* **`step6_scenarios.py`**: Runs the paper's full 48-scenario grid ($2 \text{ rules} \times 2 \text{ objectives} \times 2 \text{ value triggers} \times 2 \text{ count triggers} \times 3 \text{ time triggers}$) and exports `data/scenario_results.csv` and `data/tradeoff_chart.png`.
* **`run_all.py`**: Runs prep → step 4 → step 5 → step 6 in order.

---

## 6. Mathematical Model (Muñoz et al., 2011)

$X_{ijkl}$ is the number of shares of security $k$ settled in transaction $l$, where participant $i$ sells to participant $j$.

### Model P2 (Continuous LP)
$$\max \sum_{i,j,k,l} p_{ijkl} X_{ijkl} \quad \text{(or } \max \sum X_{ijkl} \text{ to maximize shares settled)}$$
subject to:
$$\sum_{j,l,k} p_{jikl} X_{jikl} - \sum_{j,l,k} p_{ijkl} X_{ijkl} \le C_i \quad \forall i \quad \text{(Cash Balance Constraint)}$$
$$\sum_{j,l} X_{ijkl} - \sum_{j,l} X_{jikl} \le B_{ik} \quad \forall i, k \quad \text{(Securities Balance Constraint)}$$
$$0 \le X_{ijkl} \le L_{ijkl} \quad \forall i,j,k,l \quad \text{(Trade Cap)}$$

The paper prints $X \le 0$ in P2; it must be $X \ge 0$. With unlimited credit (the default) the cash rows can never bind, so the code leaves them out.

### Model P3 (Integer Unimodular Rounding)
To prevent delivering fractional shares, bounds are constrained to:
$$I_{ijkl} \le X_{ijkl} \le I_{ijkl} + 1$$
where $I_{ijkl} = \lfloor X_{ijkl}^* \rfloor$ from P2. Cash constraints are dropped, leaving only the securities rows. Each variable appears +1 for the seller and −1 for the buyer, so the matrix is totally unimodular and the simplex solution is already integer. If those bounds are infeasible, the lower bound relaxes to 0. Any small cash overdrafts left by dropping the cash rows are covered by a trust fund and repaid from subsequent inflows. As in the paper, P3 is a rounding repair, not a guaranteed global optimum.

---

## 7. Results on Indian Data

On 240,522 real exchange trades (Day Value: ₹862.5 Crore) under 30% initial inventory coverage and unlimited credit:

| Settlement Design | % Value Settled | Avg Delay | Peak Cash Required | LP Solve Time |
| :--- | :---: | :---: | :---: | :---: |
| **Model 1: RTGS (Gross, 1-min retry)** | 98.68% | **1.07 mins** | **₹76.98 crore** | — |
| **INDEVAL Model: LP Batch (5 min)** | **98.72%** | **4.19 mins** | **₹64.01 crore** | **0.021 s** |
| **Model 3: End-of-Day Netting** | 98.81% | 138.09 mins | **₹24.91 crore** | 1.681 s |

**Key Findings:**
1. **Liquidity Savings:** Periodic 5-minute LP clearing saves about **₹13 crore (17%)** in intraday borrowing compared to RTGS; end-of-day netting saves 68% but trades wait 2.3 hours on average.
2. **Speed:** Trades settle within **4.2 minutes** on average, close to real time without the large cash drain of pure RTGS.
3. **Deadlock Resolution:** Multilateral LP batching settles slightly higher total value (98.72% vs 98.68%) because it resolves circular inventory gridlocks that freeze sequential bilateral RTGS queues.
4. **48 Scenarios:** The presettlement rule matters most. Settling gross first when funded gives 1.40–1.58 min at about ₹77 crore; sending everything to clearing gives 3.01–4.42 min at ₹67–71 crore. The fastest setting is the opposite of the cheapest one, the same speed-versus-liquidity trade-off the paper reports.
