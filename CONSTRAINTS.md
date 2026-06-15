# Financial Friction & Regulatory Rule Constraints

To preserve a micro-budget capital pool of $\le \text{₹5,000}$, all algorithmic routing decisions are bound by a rigid mathematical cost and safety matrix.

---

## 1. Indian Statutory & Brokerage Cost Matrix (Post-Budget 2026)

Every execution state must log and account for the following structural frictions:

| Metric | Cash Segment Intraday Charge Profile | Operational Application Parameter |
| :--- | :--- | :--- |
| **Brokerage Fee Floor** | Flat ₹20 per executed order | Evaluated as a flat ₹20 drag per buy and sell execution (₹40 round-trip) |
| **Securities Transaction Tax (STT)** | 0.025% Asymmetric Rate | Applied exclusively to the transaction value on the Sell Side |
| **Stamp Duty** | 0.003% Asymmetric Rate | Applied exclusively to the transaction value on the Buy Side |
| **Exchange Turnover Fee (NSE)** | 0.00307% Symmetric Rate | Applied to total turnover value (Buy Value + Sell Value) |
| **SEBI Turnover Fee** | 0.0001% Symmetric Rate | Applied to total turnover value (₹10 per Crore) |
| **Goods & Services Tax (GST)** | 18.0% Composite Tax | Levied only over the sum of (Brokerage + Exchange Fees + SEBI Fees) |

### Mathematical Fee Formulation
Because STT and Stamp Duty are exempt from GST under Indian revenue law, the friction module must compute them as independent arithmetic steps:
$$\Phi_{\text{Friction}} = 40 + (0.00025 \cdot V_{\text{sell}}) + (0.00003 \cdot V_{\text{buy}}) + 1.18 \cdot (\text{Fees}_{\text{Exchange}} + \text{Fees}_{\text{SEBI}}) + \text{Slippage}(OBI)$$

*Code Guideline:* The execution routing script must treat each individual round-trip position change as an immediate loss vector of approximately **₹41.50** to **₹45.00** depending on volume. Any completed transaction that fails to generate a minimum gross return exceeding **₹65** must be registered by the backtester as a structural net loss.

---

## 2. SEBI Daily Circuit Limits & Surveillance Controls

* **Circuit Margin Window:** No buy orders may be issued if the current stock ask price is within a 1.5% margin window of its upper daily circuit ceiling. This prevents capital from being trapped in an unhedged lockup where an operator group can execute a downside gap-opening dump on the next trading day.
* **Circuit Break Trap:** If a held asset touches a lower circuit limit, the execution module must freeze order routing, label the position as "Liquidity Locked," and immediately halt the execution thread.
* **Surveillance Blocker:** Program a filter to check the daily NSE Additional Surveillance Measure (ASM) and Graded Surveillance Measure (GSM) lists. Any asset listed under Stage 2 or higher must be permanently blacklisted from the investable universe due to margin lock and surveillance trading restrictions.

---

## 3. Security & Infrastructure Controls (SEBI 2026 Rules)

* **10 OPS Hobbyist Exemption:** The execution system must implement an interval sleep check to guarantee the system stays strictly under 10 Orders Per Second (OPS) and caps completed trades to a maximum of 2 positions per day. This qualifies the system as a "Regular API User" for personal utility, granting complete legal exemption from formal exchange strategy pre-registrations, conformance testing, and SEBI audits.
* **Session Hardening:** All API communication hooks require explicit binding to a single static whitelisted IPv4 address. Credentials must use an automated morning authentication routine utilizing OAuth-based TOTP 2FA generation to establish a fresh session token daily before 9:15 AM IST, followed by an automated logout sequence after 3:30 PM IST.
* **Integer Share Allocation Ruleset:** Fractional trading is entirely unsupported on Indian cash equities. If the calculated share count allocation yields $q_{i,t} < 1$, the execution path is automatically nullified.