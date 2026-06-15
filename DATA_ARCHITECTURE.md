# Data Architecture & Multimodal Feature Schema

This document outlines the pipeline layout, data schemas, and structural synchronization boundaries designed to bridge unstructured alternative data text with high-frequency market microstructure time series.

## 1. Storage Topology & Stream Routing
To optimize data flows without incurring infrastructure costs on a free cloud deployment, the data layer utilizes a dual-engine layout:
* **Ingestion Buffer (Redis Cloud Free):** A volatile, thread-safe, in-memory queue that buffers streaming financial text feeds and incoming 1-minute market ticks.
* **Analytical Store (SQLite3):** A persistent local database optimized for sequential read-writes, storing historically aligned spatial-temporal tensors for backtesting and parameter calibration.

## 2. Market Microstructure Stream Schema (`market_vectors`)
Captured at 15-minute intervals natively from the broker API:

| Feature Column | Data Type | Engineering / Transform Scope |
| :--- | :--- | :--- |
| `timestamp` | INTEGER | Unix Epoch milliseconds (Primary Key Partition) |
| `ticker` | TEXT | NSE Exchange Ticker Symbol (Indexed lookup, e.g., `SUZLON`) |
| `open`/`high`/`low`/`close` | REAL | Raw transaction metrics from the 15-minute bar |
| `volume` | REAL | Total traded quantity within the specific window |
| `delivery_pct` | REAL | Delivery-to-Trade ratio (Crucial for detecting intraday operator churn) |
| `order_book_imbalance` | REAL | Calculated as: $\frac{\text{BidVol} - \text{AskVol}}{\text{BidVol} + \text{AskVol}}$ |
| `wavelet_close` | REAL | Level-3 Daubechies (db4) denoised underlying price proxy |

## 3. Alternative Textual Stream Schema (`sentiment_logs`)
Scraped and updated continuously from unstructured RSS and HTML endpoints:

| Feature Column | Data Type | Engineering / Transform Scope |
| :--- | :--- | :--- |
| `item_id` | TEXT | SHA-256 hash of article URL (Enforces pipeline deduplication) |
| `timestamp` | INTEGER | Unix Epoch milliseconds of indexing time |
| `raw_text` | TEXT | Stripped headline string content |
| `sentiment_score` | REAL | Quantized FinBERT continuous scale output $\in [-1, 1]$ |
| `matched_ticker` | TEXT | Extracted ticker symbol via regex dictionary token map |
| `info_velocity` | REAL | Rolling 60-minute mention frequency acceleration |

## 4. Multi-Modal Alignment Logic (Forward-Window Join)
Because text events arrive randomly ($t_{\text{text}}$) while market observations close at discrete intervals ($t_{\text{mkt}}$), the system implements a strict forward-window synchronization join. 

All news events hitting the Redis stream within an active 15-minute bar are aggregated using a time-decay alpha multiplier:

$$\Psi_{\text{aggregated}} = \sum_{k} \text{sentiment\_score}_k \cdot e^{-\gamma (t_{\text{mkt}} - t_k)}$$

This aggregated scalar is then concatenated onto the end of the corresponding `market_vectors` record at the close of the bar, generating the complete multimodal feature space for the cross-attention layer.