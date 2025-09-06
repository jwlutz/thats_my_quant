"""
Tests for core validators - pure functions for data validation.
"""

import pytest
from datetime import date, datetime
import math
from typing import Dict, Any


# Import validators (will be created next)
from ingestion.transforms.validators import (
    validate_prices_row,
    validate_13f_row,
    ValidationError,
    check_price_date_monotonicity
)


class TestPriceValidator:
    """Tests for validate_prices_row function."""
    
    def test_valid_price_row(self):
        """Valid price row should pass validation."""
        row = {
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
        # Should not raise
        validate_prices_row(row)
    
    def test_valid_price_row_with_adj_close(self):
        """Valid price row with optional adj_close should pass."""
        row = {
            'ticker': 'AAPL',
            'date': date(2024, 1, 15),
            'open': 170.50,
            'high': 172.30,
            'low': 169.80,
            'close': 171.25,
            'adj_close': 171.00,
            'volume': 50000000,
            'source': 'yfinance',
            'as_of': date(2024, 1, 15),
            'ingested_at': datetime(2024, 1, 16, 9, 30, 0),
        }
        validate_prices_row(row)
    
    def test_missing_required_key(self):
        """Missing required key should raise ValidationError."""
        row = {
            'ticker': 'AAPL',
            # Missing 'date'
            'open': 170.50,
            'high': 172.30,
            'low': 169.80,
            'close': 171.25,
            'volume': 50000000,
            'source': 'yfinance',
            'as_of': date(2024, 1, 15),
            'ingested_at': datetime.now(),
        }
        with pytest.raises(ValidationError, match="Missing required keys.*date"):
            validate_prices_row(row)
    
    def test_invalid_price_logic(self):
        """High < Low should raise ValidationError."""
        row = {
            'ticker': 'AAPL',
            'date': date(2024, 1, 15),
            'open': 170.50,
            'high': 169.00,  # Invalid: high < low
            'low': 170.00,
            'close': 171.25,
            'volume': 50000000,
            'source': 'yfinance',
            'as_of': date(2024, 1, 15),
            'ingested_at': datetime.now(),
        }
        with pytest.raises(ValidationError, match="high.*must be >= low"):
            validate_prices_row(row)
    
    def test_negative_price(self):
        """Negative prices should raise ValidationError."""
        row = {
            'ticker': 'AAPL',
            'date': date(2024, 1, 15),
            'open': -170.50,  # Invalid: negative
            'high': 172.30,
            'low': 169.80,
            'close': 171.25,
            'volume': 50000000,
            'source': 'yfinance',
            'as_of': date(2024, 1, 15),
            'ingested_at': datetime.now(),
        }
        with pytest.raises(ValidationError, match="open.*must be positive"):
            validate_prices_row(row)
    
    def test_negative_volume(self):
        """Negative volume should raise ValidationError."""
        row = {
            'ticker': 'AAPL',
            'date': date(2024, 1, 15),
            'open': 170.50,
            'high': 172.30,
            'low': 169.80,
            'close': 171.25,
            'volume': -100,  # Invalid: negative
            'source': 'yfinance',
            'as_of': date(2024, 1, 15),
            'ingested_at': datetime.now(),
        }
        with pytest.raises(ValidationError, match="volume.*must be non-negative"):
            validate_prices_row(row)
    
    def test_infinite_values(self):
        """Infinite values should raise ValidationError."""
        row = {
            'ticker': 'AAPL',
            'date': date(2024, 1, 15),
            'open': float('inf'),  # Invalid: infinite
            'high': 172.30,
            'low': 169.80,
            'close': 171.25,
            'volume': 50000000,
            'source': 'yfinance',
            'as_of': date(2024, 1, 15),
            'ingested_at': datetime.now(),
        }
        with pytest.raises(ValidationError, match="open.*must be finite"):
            validate_prices_row(row)
    
    def test_nan_values(self):
        """NaN values should raise ValidationError."""
        row = {
            'ticker': 'AAPL',
            'date': date(2024, 1, 15),
            'open': float('nan'),  # Invalid: NaN
            'high': 172.30,
            'low': 169.80,
            'close': 171.25,
            'volume': 50000000,
            'source': 'yfinance',
            'as_of': date(2024, 1, 15),
            'ingested_at': datetime.now(),
        }
        with pytest.raises(ValidationError, match="open.*must be finite"):
            validate_prices_row(row)


class TestHoldings13FValidator:
    """Tests for validate_13f_row function."""
    
    def test_valid_13f_row(self):
        """Valid 13F row should pass validation."""
        row = {
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
        # Should not raise
        validate_13f_row(row)
    
    def test_missing_required_key(self):
        """Missing required key should raise ValidationError."""
        row = {
            'cik': '0001067983',
            'filer': 'BERKSHIRE HATHAWAY INC',
            # Missing 'ticker'
            'name': 'APPLE INC',
            'cusip': '037833100',
            'value_usd': 174800000000.0,
            'shares': 915560382.0,
            'as_of': date(2023, 12, 31),
            'source': 'sec_edgar',
            'ingested_at': datetime.now(),
        }
        with pytest.raises(ValidationError, match="Missing required keys.*ticker"):
            validate_13f_row(row)
    
    def test_negative_value_usd(self):
        """Negative value_usd should raise ValidationError."""
        row = {
            'cik': '0001067983',
            'filer': 'BERKSHIRE HATHAWAY INC',
            'ticker': 'AAPL',
            'name': 'APPLE INC',
            'cusip': '037833100',
            'value_usd': -1000.0,  # Invalid: negative
            'shares': 915560382.0,
            'as_of': date(2023, 12, 31),
            'source': 'sec_edgar',
            'ingested_at': datetime.now(),
        }
        with pytest.raises(ValidationError, match="value_usd.*must be non-negative"):
            validate_13f_row(row)
    
    def test_negative_shares(self):
        """Negative shares should raise ValidationError."""
        row = {
            'cik': '0001067983',
            'filer': 'BERKSHIRE HATHAWAY INC',
            'ticker': 'AAPL',
            'name': 'APPLE INC',
            'cusip': '037833100',
            'value_usd': 174800000000.0,
            'shares': -100.0,  # Invalid: negative
            'as_of': date(2023, 12, 31),
            'source': 'sec_edgar',
            'ingested_at': datetime.now(),
        }
        with pytest.raises(ValidationError, match="shares.*must be non-negative"):
            validate_13f_row(row)
    
    def test_invalid_cusip_length(self):
        """CUSIP must be 9 characters."""
        row = {
            'cik': '0001067983',
            'filer': 'BERKSHIRE HATHAWAY INC',
            'ticker': 'AAPL',
            'name': 'APPLE INC',
            'cusip': '12345',  # Invalid: too short
            'value_usd': 174800000000.0,
            'shares': 915560382.0,
            'as_of': date(2023, 12, 31),
            'source': 'sec_edgar',
            'ingested_at': datetime.now(),
        }
        with pytest.raises(ValidationError, match="cusip.*must be 9 characters"):
            validate_13f_row(row)


class TestDateMonotonicity:
    """Tests for date monotonicity checker."""
    
    def test_monotonic_dates(self):
        """Monotonically increasing dates should pass."""
        prices = [
            {'ticker': 'AAPL', 'date': date(2024, 1, 15)},
            {'ticker': 'AAPL', 'date': date(2024, 1, 16)},
            {'ticker': 'AAPL', 'date': date(2024, 1, 17)},
        ]
        # Should not raise
        check_price_date_monotonicity(prices)
    
    def test_non_monotonic_dates(self):
        """Non-monotonic dates should raise ValidationError."""
        prices = [
            {'ticker': 'AAPL', 'date': date(2024, 1, 15)},
            {'ticker': 'AAPL', 'date': date(2024, 1, 17)},
            {'ticker': 'AAPL', 'date': date(2024, 1, 16)},  # Out of order
        ]
        with pytest.raises(ValidationError, match="dates not monotonic"):
            check_price_date_monotonicity(prices)
    
    def test_duplicate_dates(self):
        """Duplicate dates should raise ValidationError."""
        prices = [
            {'ticker': 'AAPL', 'date': date(2024, 1, 15)},
            {'ticker': 'AAPL', 'date': date(2024, 1, 15)},  # Duplicate
            {'ticker': 'AAPL', 'date': date(2024, 1, 16)},
        ]
        with pytest.raises(ValidationError, match="Duplicate date"):
            check_price_date_monotonicity(prices)
    
    def test_multiple_tickers_separate(self):
        """Multiple tickers should be validated separately."""
        prices = [
            {'ticker': 'AAPL', 'date': date(2024, 1, 15)},
            {'ticker': 'AAPL', 'date': date(2024, 1, 16)},
            {'ticker': 'MSFT', 'date': date(2024, 1, 14)},  # OK for different ticker
            {'ticker': 'MSFT', 'date': date(2024, 1, 17)},
        ]
        # Should not raise
        check_price_date_monotonicity(prices)
    
    def test_empty_list(self):
        """Empty list should not raise."""
        check_price_date_monotonicity([])
    
    def test_single_row(self):
        """Single row should not raise."""
        prices = [{'ticker': 'AAPL', 'date': date(2024, 1, 15)}]
        check_price_date_monotonicity(prices)
