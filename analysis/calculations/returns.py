"""
Returns calculation utilities.
Pure functions for calculating simple returns over trading day windows.
"""

import numpy as np
from datetime import date
from typing import List, Dict, Union


class ReturnsError(Exception):
    """Raised when returns calculation fails."""
    pass


def window_ends(
    trading_dates: List[date], 
    windows: List[int] = [1, 5, 21, 63, 126, 252]
) -> Dict[str, int]:
    """
    Calculate how many return calculations are possible for each window.
    
    Args:
        trading_dates: List of trading dates in chronological order
        windows: List of window sizes in trading days
        
    Returns:
        Dictionary mapping window names to number of possible calculations
        
    Example:
        With 100 trading days:
        - 1D returns: 99 calculations (days 2-100)
        - 5D returns: 95 calculations (days 6-100)  
        - 21D returns: 79 calculations (days 22-100)
    """
    if not trading_dates:
        return {f"{w}D": 0 for w in windows}
    
    total_days = len(trading_dates)
    result = {}
    
    for window in windows:
        # Number of return calculations possible
        # Need at least (window + 1) days to calculate window-day returns
        # For k-day return, need k+1 prices: current + k periods back
        if total_days >= window + 1:
            possible_calculations = total_days - window
        else:
            possible_calculations = 0
        result[f"{window}D"] = possible_calculations
    
    return result


def simple_returns(prices: List[float], k: int) -> float:
    """
    Calculate simple return over k periods using most recent data.
    
    Formula: R_t,k = (P_t / P_{t-k}) - 1
    
    Args:
        prices: List of prices in chronological order
        k: Number of periods to look back
        
    Returns:
        Simple return as decimal (0.05 = 5%)
        
    Raises:
        ReturnsError: If insufficient data or invalid prices
    """
    if len(prices) < 2:
        raise ReturnsError("Insufficient data: need at least 2 prices")
    
    if k >= len(prices):
        raise ReturnsError(f"Window size {k} larger than available data {len(prices)}")
    
    if k <= 0:
        raise ReturnsError("Window size must be positive")
    
    # Check for invalid prices
    if any(p <= 0 for p in prices):
        raise ReturnsError("Zero or negative prices not allowed")
    
    # Calculate return from k periods ago to most recent
    current_price = prices[-1]  # Most recent
    past_price = prices[-1 - k]  # k periods ago
    
    return (current_price / past_price) - 1


def simple_returns_vectorized(prices: List[float], k: int) -> np.ndarray:
    """
    Calculate simple returns over k periods for all possible windows.
    
    Args:
        prices: List of prices in chronological order
        k: Number of periods to look back
        
    Returns:
        Numpy array of returns, one for each possible calculation
        
    Example:
        prices = [100, 110, 121, 115.5] with k=2:
        - Return from day 1 to day 3: (121/100) - 1 = 0.21
        - Return from day 2 to day 4: (115.5/110) - 1 = 0.05
        Returns: [0.21, 0.05]
        
        For k=3 with 3 prices [100, 120, 110]:
        - Return from day 1 to day 3: (110/100) - 1 = 0.10
        Returns: [0.10] (exactly 1 calculation)
    """
    # Need exactly k+1 prices for k-period return
    if len(prices) < k + 1:
        return np.array([])
    
    # Check for invalid prices
    if any(p <= 0 for p in prices):
        raise ReturnsError("Zero or negative prices not allowed")
    
    prices_array = np.array(prices)
    
    # Calculate returns for all possible windows
    # For k-period return, we can calculate from index k to end
    returns = []
    for i in range(k, len(prices)):
        current_price = prices_array[i]
        past_price = prices_array[i - k]
        ret = (current_price / past_price) - 1
        returns.append(ret)
    
    return np.array(returns)


def calculate_period_returns(
    prices: List[float], 
    trading_dates: List[date],
    windows: List[int] = [1, 5, 21, 63, 126, 252]
) -> Dict[str, Union[float, None]]:
    """
    Calculate returns for multiple periods, returning most recent for each.
    
    Args:
        prices: List of prices in chronological order
        trading_dates: Corresponding trading dates
        windows: Window sizes to calculate
        
    Returns:
        Dictionary mapping window names to returns (or None if insufficient data)
    """
    if len(prices) != len(trading_dates):
        raise ReturnsError("Prices and dates must have same length")
    
    if len(prices) < 2:
        return {f"{w}D": None for w in windows}
    
    # Check data availability
    window_availability = window_ends(trading_dates, windows)
    
    results = {}
    for window in windows:
        window_name = f"{window}D"
        
        if window_availability[window_name] > 0:
            # Sufficient data - calculate return
            try:
                ret = simple_returns(prices, window)
                results[window_name] = ret
            except ReturnsError:
                results[window_name] = None
        else:
            # Insufficient data
            results[window_name] = None
    
    return results
