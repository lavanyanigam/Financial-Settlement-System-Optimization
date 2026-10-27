# INDEVAL Settlement Optimization on Indian Equity Market Data

This project replicates and evaluates the Central Securities Depository clearing-and-settlement optimization model from Muñoz et al. (2011), *INDEVAL Develops a New Operating and Settlement System Using Operations Research* (Franz Edelman Award, INFORMS), using **real Indian stock exchange trade data**.

---

## 1. What This Project Does

In securities settlement, **Delivery versus Payment (DvP)** requires that the transfer of shares occurs if and only if the corresponding payment is completed.

Traditional systems face an operational trade-off:
* **Model 1 / RTGS (Real-Time Gross Settlement):** Trades settle one-by-one in real time. Settlement is fast, but requires huge cash and share inventories, creating intraday gridlocks.
* **Model 3 (End-of-Day Net Settlement):** Trades accumulate all day and are netted out at market close. Very liquidity-efficient, but settlement is delayed until end of day, leaving significant intraday risk.

**The INDEVAL Innovation ("Dalí"):**
A **continuous hybrid settlement engine** that runs periodic batches (e.g., every 5, 10, or 15 minutes) throughout the day using **Linear Programming (LP)**. The LP untangles circular delivery chains ($A \to B \to C \to A$) and unlocks frozen queues with minimal cash.

This repository implements that exact model and tests it on **240,642 real exchange trades** across **533 institutional brokers** on the Indian stock market.

---

## 2. Dataset Information

The data comes from historical Indian stock exchange audit logs (`data/Stock_Trades_Orders/Trades .csv`):
* **Trades:** Real matched transactions with quantities, prices in paise (converted to ₹ INR), and order sequence IDs.
* **Securities:** Real Indian scrip codes (e.g., `555835`, `556155`).
* **Participants:** Real exchange clearing members and broker firms (`BUY_MEMBER_CODE` and `SELL_MEMBER_CODE`, prefixed as `M<id>`).
* **Session Replay:** Real chronological trade sequences replayed across standard market hours (09:55 AM to 03:30 PM).

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
(240,642 DvP instructions)      (533 real broker members)
       │
step4_initial_balances.py
       │
       ├──> [data/initial_securities.csv] (Starting stock holdings B_ik: 30% coverage)
       └──> [data/initial_cash.csv]       (Starting cash credit lines C_i)
       │
 ┌─────┴────────────────────────────────────────────────┐
 │                                                      │
step5_netting_benefit.py                       step6_scenarios.py
• Gross vs Net comparison                      • 48-Scenario Simulation Grid
• RTGS vs 5-min LP vs EOD Netting              • Speed vs Liquidity Pareto Chart
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
To execute data cleaning, balance generation, headline comparisons, and the 48-scenario grid in one command:
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

---

## 5. File Descriptions

* **`config.py`**: Central parameter file (market hours, security coverage ratio, trigger thresholds, scenario grid).
* **`prep.py`**: Ingests raw exchange trades, converts paise to rupees, drops internal broker crosses, sequences timestamps, and generates `instructions.csv` and `participants.csv`.
* **`clearing_lp.py`**: Implements **Model P2** (continuous LP maximizing settled value or volume) and **Model P3** (totally unimodular integer rounding). Solves via SciPy's high-speed `HiGHS` solver.
* **`simulator.py`**: Event-driven settlement simulator implementing Figure 1 from the paper (presettlement rules, batch queues, triggering conditions, and trust fund overdraft tracking).
* **`step4_initial_balances.py`**: Sets initial security inventories ($B_{ik} = 30\%$ of daily sales) to simulate inventory friction, and initializes cash accounts ($C_i$).
* **`step5_netting_benefit.py`**: Computes gross vs. net liquidity requirements and compares RTGS, INDEVAL 5-minute LP clearing, and End-of-Day netting under identical initial conditions.
* **`step6_scenarios.py`**: Runs the paper's full 48-scenario grid ($2 \text{ rules} \times 2 \text{ objectives} \times 2 \text{ value triggers} \times 2 \text{ count triggers} \times 3 \text{ time triggers}$) and exports `data/scenario_results.csv` and `data/tradeoff_chart.png`.

---

## 6. Mathematical Model (Muñoz et al., 2011)

### Model P2 (Continuous LP)
$$\max \sum_{i,j,k,l} p_{ijkl} X_{ijkl}$$
subject to:
$$\sum_{j,l,k} p_{jikl} X_{jikl} - \sum_{j,l,k} p_{ijkl} X_{ijkl} \le C_i \quad \forall i \quad \text{(Cash Balance Constraint)}$$
$$\sum_{j,l} X_{ijkl} - \sum_{j,l} X_{jikl} \le B_{ik} \quad \forall i, k \quad \text{(Securities Balance Constraint)}$$
$$0 \le X_{ijkl} \le L_{ijkl} \quad \forall i,j,k,l \quad \text{(Trade Cap)}$$

### Model P3 (Integer Unimodular Rounding)
To prevent delivering fractional shares, bounds are constrained to:
$$I_{ijkl} \le X_{ijkl} \le I_{ijkl} + 1$$
where $I_{ijkl} = \lfloor X_{ijkl}^* \rfloor$ from P2. Cash constraints are temporarily relaxed, leaving the securities matrix totally unimodular, guaranteeing an exact integer solution in milliseconds. Any microscopic cash discrepancies are absorbed by a micro-credit trust fund and repaid from subsequent inflows.

---

## 7. Results on Indian Data

On 240,642 real exchange trades (Day Value: ₹862.8 Crore) under 30% initial inventory coverage:

| Settlement Design | % Value Settled | Avg Delay | Peak Cash Required | LP Solve Time |
| :--- | :---: | :---: | :---: | :---: |
| **Model 1: RTGS (Gross, 1-min retry)** | 98.68% | **1.24 mins** | **₹77.15 crore** | — |
| **INDEVAL Model: LP Batch (5 min)** | **98.72%** | **4.40 mins** | **₹67.89 crore** | **0.019 s** |
| **Model 3: End-of-Day Netting** | 98.81% | 167.49 mins | **₹24.90 crore** | 1.570 s |

**Key Findings:**
1. **Liquidity Savings:** Periodic 5-minute LP clearing saves nearly **₹10 crore** in intraday borrowing compared to RTGS.
2. **Speed:** Trades settle within **4.4 minutes** on average, providing near-instant finality without the large cash drain of pure RTGS.
3. **Deadlock Resolution:** Multilateral LP batching settles slightly higher total value (98.72% vs 98.68%) because it resolves circular inventory gridlocks that freeze sequential bilateral RTGS queues.
