"""
Schema contract tests - ensure canonical row shapes match specifications.
No database required - just dictionary validation.
"""

import pytest
from datetime import date, datetime


def test_prices_schema_contract():
    """Test that prices row has expected shape and types."""
    # Fixture: minimal valid prices row
    price_row = {
        'ticker': 'AAPL',
        'date': date(2024, 1, 15),
        'open': 170.50,
        'high': 172.30,
        'low': 169.80,
        'close': 171.25,
        'adj_close': 171.00,  # Optional field
        'volume': 50000000,
        'source': 'yfinance',
        'as_of': date(2024, 1, 15),
        'ingested_at': datetime(2024, 1, 16, 9, 30, 0),
    }
    
    # Required keys
    required_keys = {
        'ticker', 'date', 'open', 'high', 'low', 'close',
        'volume', 'source', 'as_of', 'ingested_at'
    }
    
    # Check all required keys present
    assert required_keys.issubset(price_row.keys()), \
        f"Missing required keys: {required_keys - price_row.keys()}"
    
    # Type checks
    assert isinstance(price_row['ticker'], str)
    assert isinstance(price_row['date'], date)
    assert isinstance(price_row['open'], (int, float))
    assert isinstance(price_row['high'], (int, float))
    assert isinstance(price_row['low'], (int, float))
    assert isinstance(price_row['close'], (int, float))
    assert isinstance(price_row['volume'], int)
    assert isinstance(price_row['source'], str)
    assert isinstance(price_row['as_of'], date)
    assert isinstance(price_row['ingested_at'], datetime)
    
    # Optional adj_close
    if 'adj_close' in price_row:
        assert isinstance(price_row['adj_close'], (int, float, type(None)))
    
    # Primary key components
    pk_keys = {'ticker', 'date'}
    assert pk_keys.issubset(price_row.keys())


def test_holdings_13f_schema_contract():
    """Test that holdings_13f row has expected shape and types."""
    # Fixture: minimal valid 13F row
    holding_row = {
        'cik': '0001067983',
        'filer': 'BERKSHIRE HATHAWAY INC',
        'ticker': 'AAPL',
        'name': 'APPLE INC',
        'cusip': '037833100',
        'value_usd': 174800000000.0,
        'shares': 915560382.0,
        'as_of': date(2023, 12, 31),
        'source': 'sec_edgar',
        'ingested_at': datetime(2024, 1, 16, 10, 0, 0),
    }
    
    # Required keys
    required_keys = {
        'cik', 'filer', 'ticker', 'name', 'cusip',
        'value_usd', 'shares', 'as_of', 'source', 'ingested_at'
    }
    
    # Check all required keys present
    assert required_keys.issubset(holding_row.keys()), \
        f"Missing required keys: {required_keys - holding_row.keys()}"
    
    # Type checks
    assert isinstance(holding_row['cik'], str)
    assert isinstance(holding_row['filer'], str)
    assert isinstance(holding_row['ticker'], str)
    assert isinstance(holding_row['name'], str)
    assert isinstance(holding_row['cusip'], str)
    assert isinstance(holding_row['value_usd'], (int, float))
    assert isinstance(holding_row['shares'], (int, float))
    assert isinstance(holding_row['as_of'], date)
    assert isinstance(holding_row['source'], str)
    assert isinstance(holding_row['ingested_at'], datetime)
    
    # Primary key components
    pk_keys = {'cik', 'cusip', 'as_of'}
    assert pk_keys.issubset(holding_row.keys())


def test_runs_schema_contract():
    """Test that runs row has expected shape and types."""
    # Fixture: minimal valid runs row
    run_row = {
        'run_id': 1,  # AUTO INCREMENT in real DB
        'dag_name': 'daily_prices',
        'started_at': datetime(2024, 1, 16, 9, 0, 0),
        'finished_at': datetime(2024, 1, 16, 9, 5, 30),
        'status': 'completed',
        'rows_in': 365,
        'rows_out': 365,
        'log_path': './data/logs/run_001.log',
    }
    
    # Required keys
    required_keys = {
        'run_id', 'dag_name', 'started_at', 'finished_at',
        'status', 'rows_in', 'rows_out', 'log_path'
    }
    
    # Check all required keys present
    assert required_keys.issubset(run_row.keys()), \
        f"Missing required keys: {required_keys - run_row.keys()}"
    
    # Type checks
    assert isinstance(run_row['run_id'], int)
    assert isinstance(run_row['dag_name'], str)
    assert isinstance(run_row['started_at'], datetime)
    assert isinstance(run_row['finished_at'], (datetime, type(None)))
    assert isinstance(run_row['status'], str)
    assert run_row['status'] in {'running', 'completed', 'failed'}
    assert isinstance(run_row['rows_in'], (int, type(None)))
    assert isinstance(run_row['rows_out'], (int, type(None)))
    assert isinstance(run_row['log_path'], (str, type(None)))
    
    # Primary key
    assert 'run_id' in run_row


def test_schema_fixtures_valid():
    """Test that our test fixtures are internally consistent."""
    # This test will pass once we have valid fixtures
    # It ensures our test data itself is well-formed
    
    # Price data consistency checks
    price_row = {
        'ticker': 'AAPL',
        'date': date(2024, 1, 15),
        'open': 170.50,
        'high': 172.30,
        'low': 169.80,
        'close': 171.25,
        'volume': 50000000,
        'source': 'yfinance',
        'as_of': date(2024, 1, 15),
        'ingested_at': datetime(2024, 1, 16, 9, 30, 0),
    }
    
    # High >= Low
    assert price_row['high'] >= price_row['low']
    # High >= Open and Close
    assert price_row['high'] >= price_row['open']
    assert price_row['high'] >= price_row['close']
    # Low <= Open and Close
    assert price_row['low'] <= price_row['open']
    assert price_row['low'] <= price_row['close']
    # Volume non-negative
    assert price_row['volume'] >= 0
    
    # 13F data consistency
    holding_row = {
        'value_usd': 174800000000.0,
        'shares': 915560382.0,
    }
    
    # Value and shares non-negative
    assert holding_row['value_usd'] >= 0
    assert holding_row['shares'] >= 0
