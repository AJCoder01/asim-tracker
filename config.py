"""
ASIM-Tracker: System Configuration Engine
Contains configuration loading, validation, and defaults for database, Redis,
broker APIs, trading limits, and post-Budget 2026 transaction cost parameters.
"""

import os
from pathlib import Path
from typing import Optional

# Base Workspace Directory
BASE_DIR = Path(__file__).resolve().parent

# ==============================================================================
# 1. Database & Queue Configurations
# ==============================================================================
# Persistent analytical storage
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "asim_tracker.db"))

# Volatile streaming buffer queue
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# ==============================================================================
# 2. Broker API Credentials (Angel One SmartAPI / DhanHQ)
# ==============================================================================
# Supported names: "angel_one", "dhan"
BROKER_NAME = os.getenv("BROKER_NAME", "angel_one").lower()
BROKER_CLIENT_ID = os.getenv("BROKER_CLIENT_ID", "")
BROKER_PASSWORD = os.getenv("BROKER_PASSWORD", "")
BROKER_PIN = os.getenv("BROKER_PIN", "")  # MPIN
BROKER_TOTP_KEY = os.getenv("BROKER_TOTP_KEY", "")  # Secret key for TOTP 2FA
BROKER_API_KEY = os.getenv("BROKER_API_KEY", "")
BROKER_REDIRECT_URL = os.getenv("BROKER_REDIRECT_URL", "http://127.0.0.1:5000")

# ==============================================================================
# 3. Micro-Capital & Risk Sentinel Parameters
# ==============================================================================
# Total trading budget
MAX_CAPITAL = float(os.getenv("MAX_CAPITAL", "5000.0"))

# Cardinality constraint: Max active positions at any time (||w_t||_0 <= 1)
MAX_POSITIONS = int(os.getenv("MAX_POSITIONS", "1"))

# Daily trading rate limit (personal regular API user constraint)
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "2"))

# Low-priced asset price boundary
MAX_ASSET_PRICE = float(os.getenv("MAX_ASSET_PRICE", "200.0"))

# Circuit breaker margin (abort buy if price is within 1.5% of upper ceiling)
CIRCUIT_MARGIN_PCT = float(os.getenv("CIRCUIT_MARGIN_PCT", "1.5"))

# SEBI 10 OPS limit rate throttle (sleep duration in seconds to limit execution speed)
OPS_LIMIT_SLEEP = float(os.getenv("OPS_LIMIT_SLEEP", "0.15"))

# Path to local Stage 2+ ASM / GSM blacklist registry
ASM_GSM_BLACKLIST_PATH = os.getenv(
    "ASM_GSM_BLACKLIST_PATH", str(BASE_DIR / "asm_gsm_blacklist.json")
)

# ==============================================================================
# 4. Post-Budget 2026 Transaction Cost Parameters
# ==============================================================================
# Brokerage Fee Floor (Flat ₹20 per order)
FLAT_BROKERAGE = float(os.getenv("FLAT_BROKERAGE", "20.0"))

# Securities Transaction Tax (STT) - 0.025% on Sell Side only
STT_RATE_SELL = float(os.getenv("STT_RATE_SELL", "0.00025"))

# Stamp Duty - 0.003% on Buy Side only
STAMP_DUTY_RATE_BUY = float(os.getenv("STAMP_DUTY_RATE_BUY", "0.00003"))

# Exchange Turnover Fee (NSE) - 0.00307% symmetric rate
EXCHANGE_TURNOVER_RATE = float(os.getenv("EXCHANGE_TURNOVER_RATE", "0.0000307"))

# SEBI Turnover Charge - 0.0001% symmetric rate (Rs 10 per Crore)
SEBI_TURNOVER_RATE = float(os.getenv("SEBI_TURNOVER_RATE", "0.000001"))

# GST Rate - 18% applied over (Brokerage + Exchange Charges + SEBI Fees)
GST_RATE = float(os.getenv("GST_RATE", "0.18"))

# Gross returns breakeven limit: completed trades yielding less than ₹65 is logged as net loss
BREAKEVEN_PROFIT_THRESHOLD = float(os.getenv("BREAKEVEN_PROFIT_THRESHOLD", "65.0"))

# ==============================================================================
# 5. Model Engine (DWT, FinBERT, Hawkes) Configs
# ==============================================================================
# DWT Daubechies 4 mother wavelet configurations
DWT_WAVELET_NAME = "db4"
DWT_LEVEL = 3

# Quantized FinBERT pathways
ONNX_FINBERT_PATH = os.getenv("ONNX_FINBERT_PATH", str(BASE_DIR / "model_engine" / "finbert.onnx"))
ONNX_TOKENIZER_PATH = os.getenv("ONNX_TOKENIZER_PATH", str(BASE_DIR / "model_engine" / "tokenizer"))

# Default Hawkes Point Process coefficients
DEFAULT_HAWKES_MU_0 = float(os.getenv("DEFAULT_HAWKES_MU_0", "0.01"))
DEFAULT_HAWKES_ALPHA = float(os.getenv("DEFAULT_HAWKES_ALPHA", "0.5"))
DEFAULT_HAWKES_BETA = float(os.getenv("DEFAULT_HAWKES_BETA", "1.2"))
DEFAULT_HAWKES_GAMMA = float(os.getenv("DEFAULT_HAWKES_GAMMA", "0.05"))  # Time-decay join parameter

# ==============================================================================
# Validation & Session Checks
# ==============================================================================
def validate_config() -> bool:
    """
    Performs assertions to verify configuration validity before initialization.
    """
    assert MAX_CAPITAL <= 5000.0, f"Capital pool limit exceeded: {MAX_CAPITAL} > ₹5,000"
    assert MAX_POSITIONS == 1, f"Cardinality constraint breached: {MAX_POSITIONS} != 1"
    assert MAX_TRADES_PER_DAY <= 2, f"Daily trade limit breach risk: {MAX_TRADES_PER_DAY} > 2"
    assert CIRCUIT_MARGIN_PCT >= 1.0, "Circuit breaker margin too thin"
    assert OPS_LIMIT_SLEEP >= 0.1, "10 OPS rate limit sleep must be at least 0.1s"
    return True
