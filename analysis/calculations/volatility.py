"""
Volatility calculation utilities.
Pure functions for log returns and realized volatility calculations.
"""

import numpy as np
import math
from typing import List, Union


class VolatilityError(Exception):
    """Raised when volatility calculation fails."""
    pass


def log_returns(prices: List[float]) -> np.ndarray:
    """
    Calculate log returns from price series.
    
    Formula: r_t = ln(P_t) - ln(P_{t-1}) = ln(P_t / P_{t-1})
    
    Args:
        prices: List of prices in chronological order
        
    Returns:
        Numpy array of log returns (length = len(prices) - 1)
        
    Raises:
        VolatilityError: If insufficient data or invalid prices
    """
    if len(prices) < 2:
        raise VolatilityError("Insufficient data: need at least 2 prices")
    
    # Check for invalid prices
    if any(p <= 0 for p in prices):
        raise VolatilityError("Zero or negative prices not allowed")
    
    # Convert to numpy for efficient calculation
    price_array = np.array(prices)
    
    # Calculate log returns: ln(P_t / P_{t-1})
    log_ret = np.diff(np.log(price_array))
    
    return log_ret


def realized_vol(
    log_ret: np.ndarray, 
    window: int, 
    annualize: int = 252
) -> float:
    """
    Calculate realized volatility from log returns.
    
    Formula: σ = std(log_returns) × √annualize
    
    Args:
        log_ret: Array of log returns
        window: Number of returns to use (from end of series)
        annualize: Annualization factor (252 for daily to annual)
        
    Returns:
        Annualized volatility as decimal (0.25 = 25%)
        
    Raises:
        VolatilityError: If insufficient data or invalid values
    """
    if len(log_ret) < window:
        raise VolatilityError(f"Insufficient data: need {window} returns, have {len(log_ret)}")
    
    if window <= 1:
        raise VolatilityError("Window must be > 1 for standard deviation")
    
    # Check for NaN or infinite values
    if np.any(np.isnan(log_ret)):
        raise VolatilityError("NaN values not allowed in log returns")
    
    if np.any(np.isinf(log_ret)):
        raise VolatilityError("Infinite values not allowed in log returns")
    
    # Take the most recent 'window' returns
    recent_returns = log_ret[-window:]
    
    # Calculate sample standard deviation (ddof=1)
    std_dev = np.std(recent_returns, ddof=1)
    
    # Annualize
    annualized_vol = std_dev * math.sqrt(annualize)
    
    return float(annualized_vol)


def rolling_volatility(
    log_ret: np.ndarray, 
    window: int, 
    annualize: int = 252
) -> np.ndarray:
    """
    Calculate rolling volatility over all possible windows.
    
    Args:
        log_ret: Array of log returns
        window: Rolling window size
        annualize: Annualization factor
        
    Returns:
        Array of rolling volatilities
        
    Raises:
        VolatilityError: If insufficient data
    """
    if len(log_ret) < window:
        raise VolatilityError(f"Insufficient data: need {window} returns, have {len(log_ret)}")
    
    # Check for invalid values
    if np.any(np.isnan(log_ret)):
        raise VolatilityError("NaN values not allowed in log returns")
    
    if np.any(np.isinf(log_ret)):
        raise VolatilityError("Infinite values not allowed in log returns")
    
    # Calculate rolling standard deviation
    rolling_vols = []
    
    for i in range(window - 1, len(log_ret)):
        window_returns = log_ret[i - window + 1:i + 1]
        std_dev = np.std(window_returns, ddof=1)
        annualized_vol = std_dev * math.sqrt(annualize)
        rolling_vols.append(annualized_vol)
    
    return np.array(rolling_vols)


def calculate_volatility_metrics(
    prices: List[float],
    windows: List[int] = [21, 63, 252]
) -> dict:
    """
    Calculate volatility metrics for multiple windows.
    
    Args:
        prices: List of prices in chronological order
        windows: Window sizes for volatility calculation
        
    Returns:
        Dictionary mapping window names to volatility values (or None)
    """
    if len(prices) < 2:
        return {f"{w}D_annualized": None for w in windows}
    
    try:
        # Calculate log returns
        log_ret = log_returns(prices)
        
        results = {}
        for window in windows:
            window_name = f"{window}D_annualized"
            
            if len(log_ret) >= window:
                try:
                    vol = realized_vol(log_ret, window=window, annualize=252)
                    results[window_name] = vol
                except VolatilityError:
                    results[window_name] = None
            else:
                results[window_name] = None
        
        return results
        
    except VolatilityError:
        # If log returns calculation fails, return all None
        return {f"{w}D_annualized": None for w in windows}
