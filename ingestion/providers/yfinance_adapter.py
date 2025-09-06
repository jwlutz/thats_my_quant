"""
yfinance adapter - fetch price data from Yahoo Finance.
Network IO allowed here, but minimal business logic.
"""

import yfinance as yf
import pandas as pd
from datetime import date, datetime, timedelta
from typing import Dict, Any, List


class YFinanceError(Exception):
    """Raised when yfinance operations fail."""
    pass


def fetch_prices_window(ticker: str, start: date, end: date) -> List[Dict[str, Any]]:
    """
    Fetch price data for a ticker within date window.
    Returns raw data in provider format - no normalization.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL')
        start: Start date (inclusive)
        end: End date (inclusive)
        
    Returns:
        List of raw price dictionaries in yfinance format
        
    Raises:
        YFinanceError: If fetch fails or validation fails
    """
    # Validate inputs
    _validate_date_range(start, end)
    _validate_ticker(ticker)
    
    try:
        # yfinance uses exclusive end dates, so add 1 day
        yf_end = end + timedelta(days=1)
        
        # Fetch data from yfinance
        # No progress bar for clean logs
        data = yf.download(
            ticker,
            start=start.isoformat(),
            end=yf_end.isoformat(),
            progress=False
        )
        
        # Handle empty response - check multiple ways due to yfinance API changes
        try:
            if data is None or (hasattr(data, 'empty') and data.empty) or len(data) == 0:
                return []
        except (ValueError, TypeError):
            # If checking data.empty fails, try len() check
            try:
                if len(data) == 0:
                    return []
            except:
                return []
        
        # Handle multi-level columns (when yfinance returns ticker-specific columns)
        if isinstance(data.columns, pd.MultiIndex):
            # Flatten multi-level columns - take the first level (field names)
            data.columns = data.columns.get_level_values(0)
        
        # Convert to list of dictionaries
        # Keep yfinance field names - normalization happens later
        rows = []
        for date_idx, row in data.iterrows():
            # Convert pandas Timestamp to date string
            date_str = date_idx.strftime('%Y-%m-%d')
            
            # Build row dict with yfinance field names
            row_dict = {'Date': date_str}
            
            # Add price fields if present
            for field in ['Open', 'High', 'Low', 'Close', 'Adj Close', 'Volume']:
                if field in data.columns and pd.notna(row[field]):
                    row_dict[field] = float(row[field]) if field != 'Volume' else int(row[field])
            
            rows.append(row_dict)
        
        return rows
        
    except Exception as e:
        raise YFinanceError(f"Failed to fetch prices for {ticker}: {str(e)}") from e


def _validate_date_range(start: date, end: date) -> None:
    """
    Validate date range parameters.
    
    Args:
        start: Start date
        end: End date
        
    Raises:
        YFinanceError: If validation fails
    """
    if start > end:
        raise YFinanceError(f"start date ({start}) must be <= end date ({end})")
    
    # Don't allow future dates
    today = date.today()
    if start > today or end > today:
        raise YFinanceError("Future dates not allowed for historical data")
    
    # Reasonable range limit (prevent excessive API calls)
    max_days = 365 * 3  # 3 years
    if (end - start).days > max_days:
        raise YFinanceError(f"Date range too long (max {max_days} days)")


def _validate_ticker(ticker: str) -> None:
    """
    Basic ticker validation.
    
    Args:
        ticker: Stock ticker symbol
        
    Raises:
        YFinanceError: If ticker is invalid
    """
    if not ticker or not isinstance(ticker, str):
        raise YFinanceError("Ticker must be non-empty string")
    
    if len(ticker) > 10:  # Reasonable limit
        raise YFinanceError("Ticker too long (max 10 characters)")
    
    # Allow alphanumeric plus common ticker chars
    allowed_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-')
    if not set(ticker.upper()).issubset(allowed_chars):
        raise YFinanceError(f"Ticker contains invalid characters: {ticker}")
