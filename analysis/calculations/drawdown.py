"""
Drawdown and recovery calculation utilities.
Pure functions for maximum drawdown analysis.
"""

import numpy as np
from datetime import date
from typing import List, Dict, Union, Optional


class DrawdownError(Exception):
    """Raised when drawdown calculation fails."""
    pass


def drawdown_stats(
    prices: List[float], 
    dates: List[date]
) -> Dict[str, Union[float, date, int, None]]:
    """
    Calculate maximum drawdown statistics for a price series.
    
    Finds the largest peak-to-trough decline and recovery information.
    
    Args:
        prices: List of prices in chronological order
        dates: Corresponding trading dates
        
    Returns:
        Dictionary with drawdown statistics:
        - max_drawdown_pct: Largest decline as decimal (negative)
        - peak_date: Date of peak before max drawdown
        - trough_date: Date of lowest point
        - recovery_date: Date when price exceeded peak (None if no recovery)
        - drawdown_days: Days from peak to trough
        - recovery_days: Days from trough to recovery (None if no recovery)
        
    Raises:
        DrawdownError: If insufficient data or invalid inputs
    """
    if len(prices) < 2:
        raise DrawdownError("Insufficient data: need at least 2 prices")
    
    if len(prices) != len(dates):
        raise DrawdownError("Prices and dates must have same length")
    
    if any(p <= 0 for p in prices):
        raise DrawdownError("Zero or negative prices not allowed")
    
    prices_array = np.array(prices)
    
    # Track running maximum (peak)
    running_max = np.maximum.accumulate(prices_array)
    
    # Calculate drawdown at each point
    drawdowns = (prices_array / running_max) - 1
    
    # Find maximum drawdown
    max_dd_idx = np.argmin(drawdowns)
    max_drawdown_pct = float(drawdowns[max_dd_idx])
    
    # Find the peak that led to this drawdown
    # Look backwards from max drawdown to find when running_max last increased
    peak_idx = max_dd_idx
    peak_value = running_max[max_dd_idx]
    
    # Find first occurrence of this peak value
    for i in range(max_dd_idx + 1):
        if abs(prices_array[i] - peak_value) < 1e-10:
            peak_idx = i
            break
    
    # Trough is at max drawdown index
    trough_idx = max_dd_idx
    
    # Find recovery: first price after trough that exceeds peak
    recovery_idx = None
    
    # Special case: if max drawdown is 0 (constant prices), recovery is immediate
    if abs(max_drawdown_pct) < 1e-10:  # Essentially zero drawdown
        recovery_idx = peak_idx  # Recovery at same point as peak
    else:
        # Look for actual recovery after trough
        for i in range(trough_idx + 1, len(prices_array)):
            if prices_array[i] > peak_value:
                recovery_idx = i
                break
    
    # Calculate time periods
    drawdown_days = trough_idx - peak_idx
    recovery_days = (recovery_idx - trough_idx) if recovery_idx is not None else None
    
    return {
        'max_drawdown_pct': max_drawdown_pct,
        'peak_date': dates[peak_idx],
        'trough_date': dates[trough_idx],
        'recovery_date': dates[recovery_idx] if recovery_idx is not None else None,
        'drawdown_days': drawdown_days,
        'recovery_days': recovery_days
    }


def rolling_drawdown(
    prices: List[float],
    dates: List[date], 
    window: int
) -> List[Dict[str, Union[float, date, int, None]]]:
    """
    Calculate rolling drawdown statistics over multiple windows.
    
    Args:
        prices: List of prices in chronological order
        dates: Corresponding trading dates
        window: Rolling window size
        
    Returns:
        List of drawdown statistics for each window
        
    Raises:
        DrawdownError: If insufficient data
    """
    if len(prices) < window:
        raise DrawdownError(f"Insufficient data: need {window} prices, have {len(prices)}")
    
    if len(prices) != len(dates):
        raise DrawdownError("Prices and dates must have same length")
    
    rolling_stats = []
    
    for i in range(window - 1, len(prices)):
        window_prices = prices[i - window + 1:i + 1]
        window_dates = dates[i - window + 1:i + 1]
        
        dd_stats = drawdown_stats(window_prices, window_dates)
        rolling_stats.append(dd_stats)
    
    return rolling_stats


def calculate_drawdown_metrics(
    prices: List[float],
    dates: List[date],
    min_periods: int = 10
) -> Dict[str, Union[float, date, int, None]]:
    """
    Calculate drawdown metrics with data sufficiency checks.
    
    Args:
        prices: List of prices in chronological order
        dates: Corresponding trading dates  
        min_periods: Minimum periods required for meaningful drawdown
        
    Returns:
        Dictionary with drawdown metrics (or None if insufficient data)
    """
    if len(prices) < min_periods:
        return {
            'max_drawdown_pct': None,
            'peak_date': None,
            'trough_date': None,
            'recovery_date': None,
            'drawdown_days': None,
            'recovery_days': None
        }
    
    try:
        return drawdown_stats(prices, dates)
    except DrawdownError:
        # Return null metrics if calculation fails
        return {
            'max_drawdown_pct': None,
            'peak_date': None,
            'trough_date': None,
            'recovery_date': None,
            'drawdown_days': None,
            'recovery_days': None
        }
