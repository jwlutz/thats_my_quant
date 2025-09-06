"""
Core validators for canonical data rows.
Pure functions - no IO, network, or side effects.
"""

import math
from datetime import date, datetime
from typing import Dict, Any, List, Optional


class ValidationError(ValueError):
    """Raised when data validation fails."""
    pass


def validate_prices_row(row: Dict[str, Any]) -> None:
    """
    Validate a canonical prices row.
    
    Args:
        row: Dictionary containing price data
        
    Raises:
        ValidationError: If validation fails
    """
    # Required keys
    required_keys = {
        'ticker', 'date', 'open', 'high', 'low', 'close',
        'volume', 'source', 'as_of', 'ingested_at'
    }
    
    # Check for missing keys
    missing = required_keys - set(row.keys())
    if missing:
        raise ValidationError(f"Missing required keys: {missing}")
    
    # Type validations
    if not isinstance(row['ticker'], str):
        raise ValidationError(f"ticker must be string, got {type(row['ticker'])}")
    
    if not isinstance(row['date'], date):
        raise ValidationError(f"date must be date, got {type(row['date'])}")
    
    if not isinstance(row['as_of'], date):
        raise ValidationError(f"as_of must be date, got {type(row['as_of'])}")
    
    if not isinstance(row['ingested_at'], datetime):
        raise ValidationError(f"ingested_at must be datetime, got {type(row['ingested_at'])}")
    
    if not isinstance(row['source'], str):
        raise ValidationError(f"source must be string, got {type(row['source'])}")
    
    # Numeric validations for prices
    for field in ['open', 'high', 'low', 'close']:
        value = row[field]
        if not isinstance(value, (int, float)):
            raise ValidationError(f"{field} must be numeric, got {type(value)}")
        
        if not math.isfinite(value):
            raise ValidationError(f"{field} must be finite, got {value}")
        
        if value <= 0:
            raise ValidationError(f"{field} must be positive, got {value}")
    
    # Optional adj_close validation
    if 'adj_close' in row and row['adj_close'] is not None:
        adj_close = row['adj_close']
        if not isinstance(adj_close, (int, float)):
            raise ValidationError(f"adj_close must be numeric, got {type(adj_close)}")
        
        if not math.isfinite(adj_close):
            raise ValidationError(f"adj_close must be finite, got {adj_close}")
        
        if adj_close <= 0:
            raise ValidationError(f"adj_close must be positive, got {adj_close}")
    
    # Volume validation
    volume = row['volume']
    if not isinstance(volume, int):
        raise ValidationError(f"volume must be integer, got {type(volume)}")
    
    if volume < 0:
        raise ValidationError(f"volume must be non-negative, got {volume}")
    
    # Price logic validations
    high = row['high']
    low = row['low']
    open_price = row['open']
    close = row['close']
    
    if high < low:
        raise ValidationError(f"high ({high}) must be >= low ({low})")
    
    if high < open_price:
        raise ValidationError(f"high ({high}) must be >= open ({open_price})")
    
    if high < close:
        raise ValidationError(f"high ({high}) must be >= close ({close})")
    
    if low > open_price:
        raise ValidationError(f"low ({low}) must be <= open ({open_price})")
    
    if low > close:
        raise ValidationError(f"low ({low}) must be <= close ({close})")


def validate_13f_row(row: Dict[str, Any]) -> None:
    """
    Validate a canonical 13F holdings row.
    
    Args:
        row: Dictionary containing 13F data
        
    Raises:
        ValidationError: If validation fails
    """
    # Required keys
    required_keys = {
        'cik', 'filer', 'ticker', 'name', 'cusip',
        'value_usd', 'shares', 'as_of', 'source', 'ingested_at'
    }
    
    # Check for missing keys
    missing = required_keys - set(row.keys())
    if missing:
        raise ValidationError(f"Missing required keys: {missing}")
    
    # String field validations
    for field in ['cik', 'filer', 'ticker', 'name', 'cusip', 'source']:
        if not isinstance(row[field], str):
            raise ValidationError(f"{field} must be string, got {type(row[field])}")
    
    # CUSIP must be 9 characters
    if len(row['cusip']) != 9:
        raise ValidationError(f"cusip must be 9 characters, got {len(row['cusip'])}")
    
    # Date validations
    if not isinstance(row['as_of'], date):
        raise ValidationError(f"as_of must be date, got {type(row['as_of'])}")
    
    if not isinstance(row['ingested_at'], datetime):
        raise ValidationError(f"ingested_at must be datetime, got {type(row['ingested_at'])}")
    
    # Numeric validations
    value_usd = row['value_usd']
    if not isinstance(value_usd, (int, float)):
        raise ValidationError(f"value_usd must be numeric, got {type(value_usd)}")
    
    if not math.isfinite(value_usd):
        raise ValidationError(f"value_usd must be finite, got {value_usd}")
    
    if value_usd < 0:
        raise ValidationError(f"value_usd must be non-negative, got {value_usd}")
    
    shares = row['shares']
    if not isinstance(shares, (int, float)):
        raise ValidationError(f"shares must be numeric, got {type(shares)}")
    
    if not math.isfinite(shares):
        raise ValidationError(f"shares must be finite, got {shares}")
    
    if shares < 0:
        raise ValidationError(f"shares must be non-negative, got {shares}")


def check_price_date_monotonicity(prices: List[Dict[str, Any]]) -> None:
    """
    Check that dates are monotonically increasing for each ticker.
    
    Args:
        prices: List of price rows with 'ticker' and 'date' fields
        
    Raises:
        ValidationError: If dates are not monotonic or have duplicates
    """
    if not prices:
        return
    
    # Group by ticker
    ticker_dates: Dict[str, List[date]] = {}
    for row in prices:
        ticker = row.get('ticker')
        date_val = row.get('date')
        
        if ticker not in ticker_dates:
            ticker_dates[ticker] = []
        ticker_dates[ticker].append(date_val)
    
    # Check each ticker's dates
    for ticker, dates in ticker_dates.items():
        if len(dates) <= 1:
            continue
        
        # Check for duplicates
        if len(dates) != len(set(dates)):
            raise ValidationError(f"Duplicate date found for ticker {ticker}")
        
        # Check monotonicity
        for i in range(1, len(dates)):
            if dates[i] <= dates[i-1]:
                raise ValidationError(
                    f"Ticker {ticker} dates not monotonic: "
                    f"{dates[i-1]} >= {dates[i]}"
                )
