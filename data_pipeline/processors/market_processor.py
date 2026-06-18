"""
ASIM-Tracker: Market Signal Processor
Implements Daubechies 4 (db4) 3-level Discrete Wavelet Transform (DWT) price
denoising and real-time Order Book Imbalance (OBI) calculations.
"""

import logging
import math
import numpy as np
import pywt

logger = logging.getLogger("asim_tracker.market_processor")


def denoise_close_prices(
    prices: np.ndarray,
    wavelet: str = "db4",
    level: int = 3
) -> np.ndarray:
    """
    Denoises a sequence of close prices using a multi-level Discrete Wavelet Transform (DWT).
    Filters out high-frequency microstructure noise by setting all detail coefficients 
    to zero and performing a low-pass reconstruction of the signal.

    Parameters:
    -----------
    prices : np.ndarray
        1D array of historical price series data.
    wavelet : str
        Mother wavelet name (default is 'db4').
    level : int
        Decomposition level (default is 3).

    Returns:
    --------
    np.ndarray
        Denoised price series of the same length as the input.
    """
    if not isinstance(prices, np.ndarray):
        prices = np.array(prices, dtype=float)

    n = len(prices)
    
    # Boundary Check: DWT level 3 with db4 (filter length 8) requires a minimum signal length.
    # We enforce a safe boundary limit of 16 elements. If signal is too short, we return it as is.
    if n < 16:
        logger.warning(
            f"Price array length {n} is too short for level {level} DWT with {wavelet}. "
            "Returning raw prices."
        )
        return prices

    try:
        # 1. Perform multi-level Discrete Wavelet Transform decomposition
        coeffs = pywt.wavedec(prices, wavelet, level=level)

        # 2. Zero-out all detail coefficients to leave only the smooth approximation coefficient (coeffs[0])
        # coeffs structure: [cA_n, cD_n, cD_n-1, ..., cD_1]
        for i in range(1, len(coeffs)):
            coeffs[i] = np.zeros_like(coeffs[i])

        # 3. Reconstruct the signal using inverse DWT
        reconstructed = pywt.waverec(coeffs, wavelet)

        # 4. Truncate boundary padding: waverec can output a slightly larger array than the input 
        # (e.g. +1 or +2 elements depending on parity/downsampling alignment). 
        # We slice it back to match the original input length exactly.
        return reconstructed[:n]
        
    except Exception as e:
        logger.error(f"Error occurred during DWT denoising: {e}. Returning raw prices.")
        return prices


def calculate_order_book_imbalance(bid_vol: float, ask_vol: float) -> float:
    """
    Calculates the Order Book Imbalance (OBI) factor:
    OBI = (BidVolume - AskVolume) / (BidVolume + AskVolume)
    
    Parameters:
    -----------
    bid_vol : float
        Cumulative volume of bids at best price levels.
    ask_vol : float
        Cumulative volume of asks at best price levels.
    
    Returns:
    --------
    float
        Calculated imbalance value in range [-1.0, 1.0].
        Returns 0.0 if total volume is zero.
    """
    # Protect against NaN, Inf, or invalid input volumes
    if not math.isfinite(bid_vol) or not math.isfinite(ask_vol):
        return 0.0

    total_volume = bid_vol + ask_vol
    if total_volume <= 0.0:
        return 0.0
    
    return float((bid_vol - ask_vol) / total_volume)
