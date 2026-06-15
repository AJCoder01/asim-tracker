# Backtesting Rigor & Anti-Leakage Framework

Simulating momentum strategies on low-priced assets driven by volatile news streams is highly vulnerable to optimistic bias and artificial performance inflation. This document maps out the rigid structural and mathematical boundaries enforced within our simulator to guarantee complete replication accuracy before live capital deployment.

---

## 1. Absolute Prevention of Information Leakage

### A. Look-Ahead Bias Mitigation
* **The Hazard:** Vectorized backtesting frameworks using Pandas (e.g., `.shift(-1)`) look forward into future indices during matrix transformations. This allows the machine learning models to make entry calculations at index $t$ using alternative data parameters or price metrics that would not have been indexed in production until $t+1$.
* **The Solution:** The system bypasses vectorized shortcuts and operates entirely on a strict **Event-Driven Sequential NumPy Loop**. The data stream is passed to the execution module row-by-row via a Python generator wrapper. The internal state space at step $t$ is structurally blinded to any subsequent index values in the database matrix.

### B. Execution Delay and Queue Modeling
* **The Hazard:** Assuming orders fill instantly at the 15-minute close price ignores network latency, order-routing delays, and exchange queue placement.
* **The Solution:** The simulator implements a **Next-Bar Open Execution Policy**. When a trade trigger fires at the close of candlestick $t$, the execution event is queued and executed at the opening tick of candlestick $t+1$. A variable slippage buffer is added to the open price based on the historical Order Book Imbalance ($OBI$):

$$\text{Execution Price} = P_{\text{open}, t+1} \times \left(1 + \delta_{\text{slippage}}\right)$$

$$\delta_{\text{slippage}} = \sigma_{15\text{m}} \times \left( \frac{|\text{BidVol} - \text{AskVol}|}{\text{BidVol} + \text{AskVol}} \right) \times \kappa$$

Where $\sigma_{15\text{m}}$ represents the rolling 15-minute realized volatility and $\kappa$ is a scale factor representing historical liquidity friction.

---

## 2. Post-2026 Fee and Friction Realities

To survive a micro-budget capital pool of ₹5,000, the simulator rejects uniform percentage-based cost estimates and explicitly models the discrete, asymmetric, and discontinuous statutory cash intraday matrix. 

### Indian Cash Intraday Cost Structure
The total transaction friction function $\Phi_{\text{Friction}}$ applied to each completed round-trip trade is decomposed as follows:

| Cost Component | Rate Type | Regulatory Rule Book Realities |
| :--- | :--- | :--- |
| **Brokerage Fee** | Discontinuous Flat | Flat ₹20 drag per executed order (Buy/Sell) |
| **Securities Transaction Tax (STT)** | Asymmetric | 0.025% applied **exclusively to the Sell Value** |
| **Stamp Duty** | Asymmetric | 0.003% applied **exclusively to the Buy Value** |
| **Exchange Turnover Fee (NSE)** | Symmetric | 0.00307% of total turnover (Buy Value + Sell Value) |
| **SEBI Turnover Fee** | Symmetric | 0.0001% of total turnover (Rs. 10 / Crore) |
| **Goods & Services Tax (GST)** | Composite Tax | 18% levied **only over** (Brokerage + Exchange Charges + SEBI Fees) |

### Mathematical Fee Formulation
The exact transaction-drag function subtracted from the capital pool at position clearance is structured as:

$$\Phi_{\text{Friction}} = 40 + \left(0.00025 \times V_{\text{sell}}\right) + \left(0.00003 \times V_{\text{buy}}\right) + 1.18 \times \left(\text{Fees}_{\text{Exchange}} + \text{Fees}_{\text{SEBI}}\right) + \text{Slippage}(OBI)$$

> **Operational Breakeven Constraint:** Because STT and Stamp Duty are completely exempt from GST calculations under Indian tax law, the script isolates them into separate arithmetic operations. On a small capital deployment of ₹5,000, any completed trade that generates less than **₹65 in gross profit** is evaluated as a net loss event by the simulator due to fixed brokerage drag.

---

## 3. Statistical Validity & Regime Cross-Validation

To protect against overfitting to arbitrary market environments, the historical backtest matrix isolates sequences chronologically across three distinct macro regimes:

* **Regime 1: High-Velocity Momentum (May – July 2024):** Evaluates if the multi-modal cross-attention layers can successfully latch onto rapid operator-driven volume surges during macro market rallies.
* **Regime 2: Systemic Sentiment Collapse (Late 2025):** Verifies that the Hawkes intensity decay parameter ($\beta$) accelerates stop-loss executions before liquidity locks up during structural midcap/smallcap drawdowns.
* **Regime 3: Low-Volatility Sideways Grind (Early 2026):** Confirms that the engine maintains complete capital preservation by remaining in a pure cash state when news velocity falls below the critical threshold ($\lambda_{\text{critical}}$).