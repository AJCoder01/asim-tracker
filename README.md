# ASIM-Tracker: Anomalous Sentiment Inflation & Exhaustion Tracker

ASIM-Tracker is a production-grade, real-time quantitative trading framework engineered to operate within the Cash Equity segment of the National Stock Exchange of India (NSE). It is mathematically tuned to maximize risk-adjusted returns on a retail micro-budget ($\le \text{Rs. 5,000}$) by tracking, riding, and exiting operator-driven sentiment spikes and news-induced retail FOMO.

Instead of deploying traditional Markowitz mean-variance portfolio allocation, which is fee-dilutive under flat Indian brokerage tariffs, ASIM-Tracker enforces a strict 1-sparsity cardinality constraint:
$$\|\mathbf{w}_t\|_0 \le 1$$
This constraint pools 100% of available liquidity into at most one high-conviction, low-priced asset ($P_{i,t} \le \text{Rs. 200}$) per trading window.

---

## 1. Continuous-Time Mathematical Framework

Every feature processing, intensity tracking, and parameter calibration module conforms to this two-stream stochastic differential model.

### A. Sentiment-Driven Jump-Diffusion Asset Dynamics
The continuous price action path of an unhedged equity asset $S_t$ is modeled using a modified stochastic differential equation (SDE) featuring an exogenous, non-homogeneous jump-diffusion component:
$$dS_t = \mu S_t dt + \sigma S_t dW_t + S_{t-} \left(e^{J_t} - 1\right) dN_t$$

Where:
* $\mu$ represents the underlying organic drift parameter of the stock.
* $\sigma$ represents the continuous diffusion coefficient (asset volatility) driven by standard Brownian motion ($dW_t$).
* $N_t$ is a non-homogeneous counting point process tracking discrete, anomalous price jumps induced exclusively by alternative media information shocks.
* $J_t$ is a random variable modeling the instantaneous jump magnitude, parameterized directly by the semantic polarization tensor derived from our NLP module.

### B. Self-Exciting Hawkes Process for News Intensity
Information shocks in the Indian retail market exhibit heavy clustering properties. The conditional intensity function $\lambda(t)$ of the counting jump process $N_t$ is defined as a self-exciting Hawkes process with a text-augmented activation kernel:
$$\lambda(t) = \mu_0 + \sum_{t_k < t} \alpha \cdot \mathcal{M}\left(\Psi(t_k)\right) \cdot e^{-\beta (t - t_k)}$$

Where:
* $\mu_0$ is the baseline background arrival rate of corporate actions or routine exchange disclosures.
* $t_k$ represents the exact historical Unix millisecond timestamp when alternative data news event $k$ was indexed by our scrapers.
* $\alpha$ is the intensity jump amplification multiplier following a shock.
* $\beta$ is the exponential decay coefficient modeling market memory and information exhaustion (velocity at which retail attention dissipates and operators unwind inventory).
* $\mathcal{M}(\Psi(t_k)) \in [-1, 1]$ is a continuous scaling mapping of the extracted multi-dimensional text tensor $\Psi$ output by our quantized financial language transformer model.

---

## 2. Multimodal Deep Learning & Cross-Attention Alignment

To protect the system from executing on low-volume media chatter or illiquid "fake news," the unstructured textual tensor stream is structurally aligned with the order-book microstructure data stream via a bilinear cross-attention fusion network:

```
[Raw Intraday 15m Candles + OBI] ──> [Level-3 db4 Wavelet DWT Transformer] ──> H_mkt
                                                                                  │
                                                                                  ▼
                                                                        [Bilinear Cross-Attention]
                                                                                  ▲
                                                                                  │
[Scraped Live Alternative Feeds] ──> [ONNX-Quantized FinBERT Engine]     ──> H_text
```

### A. The Structural Market Processing Layer
Raw 15-minute close price arrays pass through a 3-level Discrete Wavelet Transform (DWT) utilizing a Daubechies 4 (`db4`) mother wavelet to isolate underlying low-frequency trends from high-frequency noise. Concurrently, the Order Book Imbalance (OBI) is calculated to monitor institutional absorption:
$$OBI_t = \frac{\text{BidVolume}_t - \text{AskVolume}_t}{\text{BidVolume}_t + \text{AskVolume}_t}$$
These elements compile into the market microstructure hidden state matrix $\mathbf{H}_{\text{mkt}}$.

### B. The Textual Sentiment Extraction Layer
Unstructured news strings scraped from RSS and HTML feeds are processed by an ONNX Runtime quantized FinBERT engine to output low-latency token representations. Compiled with a rolling 60-minute information velocity index, they form the textual hidden state matrix $\mathbf{H}_{\text{text}}$.

### C. Bilinear Cross-Attention Core
The system queries the market state against the textual matrix to verify if a volume breakout is fundamentally supported by matching narrative intensity:
$$\mathbf{A} = \text{Softmax}\left( \frac{(\mathbf{H}_{\text{mkt}}\mathbf{W}_Q)(\mathbf{H}_{\text{text}}\mathbf{W}_K)^{\top}}{\sqrt{d_k}} \right)$$
$$\mathbf{H}_{\text{fused}} = \mathbf{A}(\mathbf{H}_{\text{text}}\mathbf{W}_V) \odot \mathbf{H}_{\text{mkt}}$$

Where $\mathbf{W}_Q, \mathbf{W}_K, \mathbf{W}_V$ represent learned linear projection weights, $d_k$ is the normalization scale dimension, and $\odot$ denotes the Hadamard product. If a sentiment spike lacks a corresponding order-book liquidity footprint, the weights inside matrix $\mathbf{A}$ force the fused representation toward zero, suppressing false trading signals.

---

## 3. Production Software Architecture

The framework is organized as a decoupled, asynchronous multi-threaded layout:
* **Data Pipeline Scrapers:** Built via `asyncio` and `aiohttp` to poll news RSS boards and exchange corporate HTML disclosures concurrently. Pushes raw text items to an in-memory Redis TimeSeries buffer.
* **Analytical Storage Engine:** An indexed local SQLite3 database that acts as the persistent system log. It joins Redis text records to historical 15-minute price candles using a strict forward-window synchronization join boundary:
  $$\text{Window} = [t_{\text{mkt}} - 15\text{m}, t_{\text{mkt}}]$$
* **Execution Controller:** Connects with the Angel One SmartAPI / DhanHQ API platforms using zero-cost retail data sockets.
* **Backtesting Simulator:** Built completely from scratch using sequential NumPy event-driven loops. Vectorized Pandas operations are strictly banned across the backtesting core to eliminate historical look-ahead bias.

---

## 4. Strict SEBI Compliance & Friction Matrix

### A. The 10 OPS Hobbyist Exemption Rule
Under the SEBI Algorithmic Trading Compliance Framework, automated order routing must remain strictly under 10 Orders Per Second (OPS). By throttling execution to under 10 OPS and capping total completed trades to a maximum of 2 positions per day, the script qualifies as a "Regular API User" for personal utility and is exempt from formal exchange strategy pre-registrations, conformance testing, and SEBI audits.

### B. Session Hardening & Security
* **Session Limits:** Authenticates via an OAuth-based TOTP 2FA routine daily before 9:15 AM IST and automatically logs out after 3:30 PM IST.
* **IP Whitelisting:** Restricted to a single static whitelisted IPv4 cloud address.
* **Order Typology:** Strictly routes LIMIT orders pegged to the prevailing best-ask price to eliminate slippage hazards. Each order contains the broker-assigned unique Algo-ID compliance tag.

### C. Post-Budget 2026 Friction Engine
Calculates the exact asymmetric Indian statutory cash intraday fee matrix:
$$\Phi_{\text{Friction}} = 40 + (0.00025 \cdot V_{\text{sell}}) + (0.00003 \cdot V_{\text{buy}}) + 1.18 \cdot (\text{Fees}_{\text{Exchange}} + \text{Fees}_{\text{SEBI}}) + \text{Slippage}(OBI)$$

| Cost Component | Rate Type | Operational Application Parameter |
| :--- | :--- | :--- |
| **Brokerage Fee Floor** | Flat Rs. 20 per executed order | Evaluated as a flat Rs. 20 drag per buy and sell execution (Rs. 40 round-trip) |
| **Securities Transaction Tax (STT)** | 0.025% Asymmetric Rate | Applied exclusively to the transaction value on the Sell Side |
| **Stamp Duty** | 0.003% Asymmetric Rate | Applied exclusively to the transaction value on the Buy Side |
| **Exchange Turnover Fee (NSE)** | 0.00307% Symmetric Rate | Applied to total turnover value (Buy Value + Sell Value) |
| **SEBI Turnover Charge** | 0.0001% Symmetric Rate | Applied to total turnover value (Rs. 10 per Crore) |
| **Goods & Services Tax (GST)** | 18.0% Composite Tax | Levied only over the sum of (Brokerage + Exchange Fees + SEBI Fees) |

Any completed transaction that fails to generate a minimum gross return exceeding **Rs. 65** is registered as a structural net loss.

### D. Daily Circuit Breaker Sentinels
* **Circuit Margin Window:** Aborts order routing instantly if the current asset ask price is within 1.5% of the upper circuit ceiling.
* **Blacklisting:** Permanently blacklists assets placed on the NSE's Additional Surveillance Measure (ASM) or Graded Surveillance Measure (GSM) lists at Stage 2 or higher.

---

## 5. Directory Layout

The workspace components are linked below:

* **Core Configuration & Entry points:**
  * [`config.py`](file:///Users/ayush/everything/Projects/asim-tracker/config.py): Centralized system configurations and parameter validations.
  * [`main.py`](file:///Users/ayush/everything/Projects/asim-tracker/main.py): Main coordination event loop and execution entry point.
* **Documentation Guides:**
  * [`PLAN.md`](file:///Users/ayush/everything/Projects/asim-tracker/PLAN.md): Project roadmaps and granular atomic task lists.
  * [`CONSTRAINTS.md`](file:///Users/ayush/everything/Projects/asim-tracker/CONSTRAINTS.md): Financial cost equations and regulatory compliance parameters.
  * [`DATA_ARCHITECTURE.md`](file:///Users/ayush/everything/Projects/asim-tracker/DATA_ARCHITECTURE.md): Database stream schemas and multimodal forward-window joins.
  * [`BACKTEST_METHODOLOGY.md`](file:///Users/ayush/everything/Projects/asim-tracker/BACKTEST_METHODOLOGY.md): Event-driven simulator parameters and backtest regimes.
* **Data Ingestion & Processing (`data_pipeline/`):**
  * [`data_pipeline/database/db_client.py`](file:///Users/ayush/everything/Projects/asim-tracker/data_pipeline/database/db_client.py): Local SQLite3 initialization and synchronization queries.
  * [`data_pipeline/scrapers/news_scraper.py`](file:///Users/ayush/everything/Projects/asim-tracker/data_pipeline/scrapers/news_scraper.py): Asynchronous web scraper polling alternative news RSS feeds.
  * [`data_pipeline/scrapers/redis_queue.py`](file:///Users/ayush/everything/Projects/asim-tracker/data_pipeline/scrapers/redis_queue.py): Redis connection pool manager buffering live streams.
  * [`data_pipeline/processors/text_processor.py`](file:///Users/ayush/everything/Projects/asim-tracker/data_pipeline/processors/text_processor.py): Quantized ONNX FinBERT model handling sentiment score mapping.
  * [`data_pipeline/processors/market_processor.py`](file:///Users/ayush/everything/Projects/asim-tracker/data_pipeline/processors/market_processor.py): Level-3 DWT filter configurations and OBI calculations.
* **Quantitative Modeling (`model_engine/`):**
  * [`model_engine/networks.py`](file:///Users/ayush/everything/Projects/asim-tracker/model_engine/networks.py): Bilinear cross-attention module in PyTorch.
  * [`model_engine/optimization.py`](file:///Users/ayush/everything/Projects/asim-tracker/model_engine/optimization.py): Hawkes process MLE parameter estimator.
  * [`model_engine/loss.py`](file:///Users/ayush/everything/Projects/asim-tracker/model_engine/loss.py): Custom target losses.
* **Execution Sentinel (`execution_system/`):**
  * [`execution_system/broker_api.py`](file:///Users/ayush/everything/Projects/asim-tracker/execution_system/broker_api.py): Handles TOTP 2FA daily sessions and resets.
  * [`execution_system/order_routing.py`](file:///Users/ayush/everything/Projects/asim-tracker/execution_system/order_routing.py): Under 10 OPS pegged limit order transmitter.
  * [`execution_system/sentinel.py`](file:///Users/ayush/everything/Projects/asim-tracker/execution_system/sentinel.py): Circuit breakers and stage 2+ ASM/GSM asset blacklist watchdogs.
* **Backtester Loop (`backtester/`):**
  * [`backtester/event_driven.py`](file:///Users/ayush/everything/Projects/asim-tracker/backtester/event_driven.py): NumPy chronological event-driven simulator.