# Project Implementation Plan & Milestones

This plan maps out the decoupled engineering sprint sequences and granular implementation tasks required to construct the ASIM-Tracker from zero to production-grade paper-deployment stage.

---

## Milestone 1: Async Ingestion & 2FA Infrastructure

### A. Configuration & Authentication Core
- [x] Implement `config.py` to parse environment variables (API credentials, Redis/SQLite URIs, risk thresholds, NSE fee rates).
- [ ] Build `execution_system/broker_api.py` to implement pre-market OAuth/TOTP 2FA daily login routine (triggered before 9:15 AM IST).
- [ ] Implement automated afternoon session cleanup and logout sequence in `execution_system/broker_api.py` (after 3:30 PM IST).
- [ ] Configure static IPv4 whitelisting parameters within API requests.

### B. Ingestion Buffer & RSS Scrapers
- [ ] Create `data_pipeline/scrapers/redis_queue.py` as the thread-safe connection pool for Redis TimeSeries.
- [ ] Implement Redis push/pop operations for incoming news streams and 1-minute ticker updates.
- [ ] Build `data_pipeline/scrapers/news_scraper.py` using `asyncio` and `aiohttp` to poll news RSS boards and HTML announcements.
- [ ] Write regex token matching in scrapers to associate articles to ticker symbols (e.g., "Suzlon Energy" -> `SUZLON`).

### C. Persistent Database Store
- [ ] Implement database initialization in `data_pipeline/database/db_client.py` for SQLite tables `market_vectors` and `sentiment_logs`.
- [ ] Write the forward-window synchronization join function in `db_client.py` utilizing the time-decay aggregation query:
  $$\Psi_{\text{aggregated}} = \sum_{k} \text{sentiment\_score}_k \cdot e^{-\gamma (t_{\text{mkt}} - t_k)}$$
  for the active window $[t_{\text{mkt}} - 15\text{m}, t_{\text{mkt}}]$.

---

## Milestone 2: Wavelet Denoising & Sentiment Tokenization

### A. Market Signal Processing
- [ ] Implement Daubechies 4 (`db4`) 3-level Discrete Wavelet Transform (DWT) in `data_pipeline/processors/market_processor.py` using `PyWavelets`.
- [ ] Implement real-time Order Book Imbalance (OBI) calculator in `market_processor.py`:
  $$OBI_t = \frac{\text{BidVolume}_t - \text{AskVolume}_t}{\text{BidVolume}_t + \text{AskVolume}_t}$$

### B. ONNX FinBERT Sentiment Engine
- [ ] Export the pre-trained `ProsusAI/finbert` model into ONNX format.
- [ ] Build `data_pipeline/processors/text_processor.py` to load the ONNX-quantized model and execute tokenization + inference on CPU.
- [ ] Write rolling 60-minute information velocity tracker (mention acceleration index).

---

## Milestone 3: Mathematics Formulation & Modeling

### A. Hawkes Intensity Calibration
- [ ] Build Maximum Likelihood Estimation (MLE) optimization routine in `model_engine/optimization.py` to fit intensity parameters ($\alpha, \beta, \mu_0$):
  $$\lambda(t) = \mu_0 + \sum_{t_k < t} \alpha \cdot \mathcal{M}\left(\Psi(t_k)\right) \cdot e^{-\beta (t - t_k)}$$

### B. Bilinear Cross-Attention Network (PyTorch)
- [ ] Build `model_engine/networks.py` implementing the bilinear attention network in PyTorch.
- [ ] Implement query ($\mathbf{W}_Q$), key ($\mathbf{W}_K$), and value ($\mathbf{W}_V$) projection layers for market ($\mathbf{H}_{\text{mkt}}$) and textual ($\mathbf{H}_{\text{text}}$) states.
- [ ] Code attention matrix calculations:
  $$\mathbf{A} = \text{Softmax}\left( \frac{(\mathbf{H}_{\text{mkt}}\mathbf{W}_Q)(\mathbf{H}_{\text{text}}\mathbf{W}_K)^{\top}}{\sqrt{d_k}} \right)$$
- [ ] Write Hadamard fusion matrix multiplication:
  $$\mathbf{H}_{\text{fused}} = \mathbf{A}(\mathbf{H}_{\text{text}}\mathbf{W}_V) \odot \mathbf{H}_{\text{mkt}}$$
- [ ] Implement Gumbel-Softmax or Top-K sparsity selection in `model_engine/networks.py` to enforce the single-asset constraint $\|\mathbf{w}\|_0 \le 1$ and stock price filter ($P \le \text{₹200}$).
- [ ] Code sentiment target loss modules in `model_engine/loss.py`.

---

## Milestone 4: Event-Driven Backtesting Engine

### A. Event Loop & Execution Modeling
- [ ] Build row-by-row simulation loop in `backtester/event_driven.py` using NumPy.
- [ ] Implement Python generator wrapper to feed historical matrix slices sequentially (preventing look-ahead leakage).
- [ ] Implement Next-Bar Open execution logic with OBI-based slippage calculations:
  $$\delta_{\text{slippage}} = \sigma_{15\text{m}} \times \left( \frac{|\text{BidVol} - \text{AskVol}|}{\text{BidVol} + \text{AskVol}} \right) \times \kappa$$

### B. Asymmetric Indian Transaction Fee Matrix
- [ ] Write tax and fee engine in `backtester/event_driven.py` implementing post-Budget 2026 statutory rates:
  - Brokerage: flat ₹20 per order
  - STT: 0.025% on Sell value
  - Stamp Duty: 0.003% on Buy value
  - Exchange Turnover: 0.00307% on total turnover
  - SEBI Fee: 0.0001% on total turnover
  - GST: 18.0% over (Brokerage + Exchange + SEBI)
- [ ] Implement the ₹65 gross return breakeven logic (flagging smaller gains as structural net losses).

### C. Performance Analytics
- [ ] Code Sharpe Ratio, Downside Semi-Deviation, and Maximum Drawdown calculators in `backtester/event_driven.py`.
- [ ] Set up backtest runs across the three macro regimes: High-Velocity Momentum (mid-2024), Sentiment Collapse (late 2025), and Sideways Grind (early 2026).

---

## Milestone 5: Automation & Sentinel Integration

### A. Live Socket Client & Order Routing
- [ ] Implement live data socket listeners for Level-3 book depth and tick data feeds in `execution_system/broker_api.py`.
- [ ] Implement LIMIT order routing pegged to the best-ask price with unique Algo-ID compliance tag in `execution_system/order_routing.py`.
- [ ] Build the main 15-minute coordination executor loop in `main.py`.

### B. Compliance Guardrails & Risk Sentinels
- [ ] Implement internal order throttle limiting execution to under 10 OPS in `order_routing.py`.
- [ ] Implement max 2 completed trades per day ceiling.
- [ ] Code the Upper Circuit margin limit watchdog in `execution_system/sentinel.py` (abort buy if price is within 1.5% of upper ceiling).
- [ ] Code the Lower Circuit trap (freeze routing on lower limit, mark position "Liquidity Locked").
- [ ] Implement daily Stage 2+ ASM and GSM surveillance blacklist filters in `sentinel.py`.
- [ ] Implement capital rounding limits ensuring total deployment remains strictly $\le \text{₹5,000}$.