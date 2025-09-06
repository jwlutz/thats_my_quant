"""
Normalizers for transforming provider data to canonical shape.
Pure functions - no IO, network, or side effects.
Minimal normalization - only when necessary.
"""

from datetime import date, datetime
from typing import Dict, Any, List, Optional


class TickerMappingError(Exception):
    """Raised when ticker cannot be determined from data."""
    pass


def normalize_prices(
    raw_rows: List[Dict[str, Any]],
    *,
    ticker: str,
    source: str,
    as_of: date,
    ingested_at: datetime
) -> List[Dict[str, Any]]:
    """
    Transform provider-native price rows to canonical shape.
    
    Minimal normalization:
    - Date strings to date objects (required for schema)
    - Field name mapping (provider uses different names)
    - Deduplication by date (keep last to handle corrections)
    
    Args:
        raw_rows: List of provider-specific price dictionaries
        ticker: Stock ticker symbol
        source: Data provider name
        as_of: Date when data was fetched (usually same as data date)
        ingested_at: Pipeline processing timestamp
        
    Returns:
        List of canonical price dictionaries
    """
    if not raw_rows:
        return []
    
    normalized = []
    seen_dates = {}  # For deduplication
    
    for raw in raw_rows:
        # Parse date - yfinance uses "Date" field
        # Normalization justified: Schema requires date object, provider gives string
        date_str = raw.get('Date', '')
        if isinstance(date_str, str):
            row_date = date.fromisoformat(date_str)
        else:
            row_date = date_str
        
        # Build canonical row
        # Field mapping justified: Provider uses different field names than our schema
        canonical = {
            'ticker': ticker,
            'date': row_date,
            'open': float(raw.get('Open', 0)),
            'high': float(raw.get('High', 0)),
            'low': float(raw.get('Low', 0)),
            'close': float(raw.get('Close', 0)),
            'adj_close': float(raw['Adj Close']) if 'Adj Close' in raw else None,
            'volume': int(raw.get('Volume', 0)),
            'source': source,
            'as_of': row_date,  # For prices, as_of typically equals data date
            'ingested_at': ingested_at,
        }
        
        # Deduplication by primary key (ticker, date)
        # Justified: Prevents PK violations, keeps latest correction
        pk = (ticker, row_date)
        seen_dates[pk] = canonical
    
    # Return deduplicated rows in original order
    return list(seen_dates.values())


def normalize_13f(
    raw_rows: List[Dict[str, Any]],
    *,
    source: str,
    as_of: date,
    ingested_at: datetime
) -> List[Dict[str, Any]]:
    """
    Transform provider-native 13F rows to canonical shape.
    
    Minimal normalization:
    - Value from thousands to dollars (if needed)
    - Ticker inference from issuer name (best effort)
    - CIK padding to 10 digits (SEC standard)
    - Deduplication by (cik, cusip, as_of)
    
    Args:
        raw_rows: List of provider-specific 13F dictionaries
        source: Data provider name (usually 'sec_edgar')
        as_of: Reporting period end date
        ingested_at: Pipeline processing timestamp
        
    Returns:
        List of canonical 13F holdings dictionaries
    """
    if not raw_rows:
        return []
    
    normalized = []
    seen_holdings = {}  # For deduplication
    
    for raw in raw_rows:
        # Get CIK and pad to 10 digits (SEC standard format)
        # Normalization justified: SEC uses 10-digit CIKs consistently
        cik = str(raw.get('CIK', '')).zfill(10)
        
        # Get filer name
        filer = raw.get('Company Name', '')
        
        # Infer ticker from issuer name (best effort)
        # This is a simple mapping - could be enhanced with a mapping table
        ticker = _infer_ticker(raw.get('nameOfIssuer', ''))
        
        # Get CUSIP (already 9 chars from SEC)
        cusip = raw.get('cusip', '')
        
        # Values - ensure they're in dollars (not thousands)
        # SEC reports in thousands, we store in dollars
        # Normalization justified: Consistent units across all data
        value_raw = float(raw.get('value', 0))
        # Check if value seems to be in thousands (typical for 13F)
        # This is a heuristic - values under 1M likely in thousands
        if value_raw < 1000000:
            value_usd = value_raw * 1000  # Convert from thousands
        else:
            value_usd = value_raw
        
        shares = float(raw.get('shares', 0))
        
        # Build canonical row
        canonical = {
            'cik': cik,
            'filer': filer,
            'ticker': ticker,
            'name': raw.get('nameOfIssuer', ''),
            'cusip': cusip,
            'value_usd': value_usd,
            'shares': shares,
            'as_of': as_of,
            'source': source,
            'ingested_at': ingested_at,
        }
        
        # Deduplication by primary key (cik, cusip, as_of)
        # Justified: Prevents PK violations, keeps latest filing
        pk = (cik, cusip, as_of)
        seen_holdings[pk] = canonical
    
    return list(seen_holdings.values())


def _infer_ticker(issuer_name: str) -> str:
    """
    Infer ticker symbol from issuer name.
    Simple mapping for common stocks - could be enhanced.
    
    Args:
        issuer_name: Company name from 13F filing
        
    Returns:
        Ticker symbol or 'UNKNOWN' if cannot infer
    """
    # Simple mapping table - in production would use comprehensive mapping
    # Normalization justified: Need ticker for joins with price data
    ticker_map = {
        'APPLE INC': 'AAPL',
        'MICROSOFT CORP': 'MSFT',
        'AMAZON COM INC': 'AMZN',
        'ALPHABET INC': 'GOOGL',
        'BANK OF AMERICA CORP': 'BAC',
        'BERKSHIRE HATHAWAY INC': 'BRK.B',
        'JPMORGAN CHASE & CO': 'JPM',
        'JOHNSON & JOHNSON': 'JNJ',
        'VISA INC': 'V',
        'PROCTER & GAMBLE CO': 'PG',
        # Add more mappings as needed
    }
    
    # Clean and uppercase for matching
    clean_name = issuer_name.upper().strip()
    
    # Direct lookup
    if clean_name in ticker_map:
        return ticker_map[clean_name]
    
    # Partial match for variations
    for key, ticker in ticker_map.items():
        if key in clean_name or clean_name in key:
            return ticker
    
    # Cannot infer
    return 'UNKNOWN'
