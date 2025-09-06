"""
Tests for normalizer functions - transform provider data to canonical shape.
Using golden fixtures for exact output validation.
"""

import json
import pytest
from datetime import date, datetime
from pathlib import Path

# Import normalizers (will be created next)
from ingestion.transforms.normalizers import (
    normalize_prices,
    normalize_13f,
    TickerMappingError
)


class TestPriceNormalizer:
    """Tests for normalize_prices function."""
    
    def load_fixture(self, filename):
        """Load JSON fixture from golden directory."""
        fixture_path = Path(__file__).parent.parent.parent / 'tests/fixtures/golden' / filename
        with open(fixture_path, 'r') as f:
            return json.load(f)
    
    def test_normalize_yfinance_data(self):
        """Test normalizing yfinance raw data to canonical shape."""
        # Load fixtures
        raw_data = self.load_fixture('yfinance_aapl_raw.json')
        expected = self.load_fixture('yfinance_aapl_normalized.json')
        
        # Fixed ingestion time for reproducibility
        ingested_at = datetime(2024, 1, 16, 9, 0, 0)
        
        # Normalize
        result = normalize_prices(
            raw_data['data'],
            ticker='AAPL',
            source='yfinance',
            as_of=date(2024, 1, 16),  # When we fetched it
            ingested_at=ingested_at
        )
        
        # Convert dates back to strings for comparison
        for row in result:
            row['date'] = row['date'].isoformat()
            row['as_of'] = row['as_of'].isoformat()
            row['ingested_at'] = row['ingested_at'].isoformat()
        
        # Compare with expected
        assert len(result) == len(expected['data'])
        for actual, exp in zip(result, expected['data']):
            assert actual == exp
    
    def test_normalize_empty_list(self):
        """Empty input should return empty list."""
        result = normalize_prices(
            [],
            ticker='AAPL',
            source='yfinance',
            as_of=date(2024, 1, 16),
            ingested_at=datetime.now()
        )
        assert result == []
    
    def test_normalize_preserves_order(self):
        """Normalization should preserve row order."""
        raw_data = self.load_fixture('yfinance_aapl_raw.json')
        
        result = normalize_prices(
            raw_data['data'],
            ticker='AAPL',
            source='yfinance',
            as_of=date(2024, 1, 16),
            ingested_at=datetime.now()
        )
        
        # Check dates are in same order
        dates = [row['date'] for row in result]
        assert dates == [date(2024, 1, 15), date(2024, 1, 16)]
    
    def test_normalize_handles_missing_adj_close(self):
        """Handle missing Adj Close field gracefully."""
        raw_data = [
            {
                "Date": "2024-01-15",
                "Open": 185.25,
                "High": 186.80,
                "Low": 184.50,
                "Close": 185.92,
                # No Adj Close
                "Volume": 65284300
            }
        ]
        
        result = normalize_prices(
            raw_data,
            ticker='AAPL',
            source='yfinance',
            as_of=date(2024, 1, 15),
            ingested_at=datetime.now()
        )
        
        assert len(result) == 1
        assert result[0]['adj_close'] is None
    
    def test_normalize_pk_uniqueness(self):
        """Primary key (ticker, date) must be unique."""
        # Duplicate dates in raw data
        raw_data = [
            {
                "Date": "2024-01-15",
                "Open": 185.25,
                "High": 186.80,
                "Low": 184.50,
                "Close": 185.92,
                "Volume": 65284300
            },
            {
                "Date": "2024-01-15",  # Duplicate date
                "Open": 186.10,
                "High": 187.45,
                "Low": 185.80,
                "Close": 187.11,
                "Volume": 58414500
            }
        ]
        
        # Should raise or deduplicate - let's expect deduplication keeping last
        result = normalize_prices(
            raw_data,
            ticker='AAPL',
            source='yfinance',
            as_of=date(2024, 1, 15),
            ingested_at=datetime.now()
        )
        
        # Should only have one row for the date
        assert len(result) == 1
        assert result[0]['open'] == 186.10  # Last row's values


class TestHoldings13FNormalizer:
    """Tests for normalize_13f function."""
    
    def load_fixture(self, filename):
        """Load JSON fixture from golden directory."""
        fixture_path = Path(__file__).parent.parent.parent / 'tests/fixtures/golden' / filename
        with open(fixture_path, 'r') as f:
            return json.load(f)
    
    def test_normalize_13f_data(self):
        """Test normalizing 13F raw data to canonical shape."""
        # Load fixtures
        raw_data = self.load_fixture('13f_berkshire_raw.json')
        expected = self.load_fixture('13f_berkshire_normalized.json')
        
        # Fixed ingestion time for reproducibility
        ingested_at = datetime(2024, 1, 16, 10, 0, 0)
        
        # Normalize
        result = normalize_13f(
            raw_data['data'],
            source='sec_edgar',
            as_of=date(2023, 9, 30),  # Report period end
            ingested_at=ingested_at
        )
        
        # Convert dates back to strings for comparison
        for row in result:
            row['as_of'] = row['as_of'].isoformat()
            row['ingested_at'] = row['ingested_at'].isoformat()
        
        # Compare with expected
        assert len(result) == len(expected['data'])
        for actual, exp in zip(result, expected['data']):
            assert actual == exp
    
    def test_normalize_13f_empty_list(self):
        """Empty input should return empty list."""
        result = normalize_13f(
            [],
            source='sec_edgar',
            as_of=date(2023, 9, 30),
            ingested_at=datetime.now()
        )
        assert result == []
    
    def test_normalize_13f_ticker_inference(self):
        """Test ticker inference from issuer name."""
        raw_data = [
            {
                "nameOfIssuer": "APPLE INC",
                "cusip": "037833100",
                "value": 174800000,
                "shares": 915560382,
                "Company Name": "BERKSHIRE HATHAWAY INC",
                "CIK": "0001067983"
            }
        ]
        
        result = normalize_13f(
            raw_data,
            source='sec_edgar',
            as_of=date(2023, 9, 30),
            ingested_at=datetime.now()
        )
        
        # Should infer AAPL ticker from APPLE INC
        assert result[0]['ticker'] == 'AAPL'
    
    def test_normalize_13f_handles_missing_fields(self):
        """Handle missing optional fields gracefully."""
        raw_data = [
            {
                "nameOfIssuer": "SOME COMPANY",
                "cusip": "123456789",
                "value": 1000000,
                "shares": 50000,
                "Company Name": "TEST FILER",
                "CIK": "0000000001"
                # No putCall, shareType, etc.
            }
        ]
        
        result = normalize_13f(
            raw_data,
            source='sec_edgar',
            as_of=date(2023, 9, 30),
            ingested_at=datetime.now()
        )
        
        assert len(result) == 1
        assert result[0]['cusip'] == '123456789'
        assert result[0]['ticker'] == 'UNKNOWN'  # Can't infer
    
    def test_normalize_13f_pk_uniqueness(self):
        """Primary key (cik, cusip, as_of) must be unique."""
        # Duplicate cusip for same filer
        raw_data = [
            {
                "nameOfIssuer": "APPLE INC",
                "cusip": "037833100",
                "value": 174800000,
                "shares": 915560382,
                "Company Name": "BERKSHIRE HATHAWAY INC",
                "CIK": "0001067983"
            },
            {
                "nameOfIssuer": "APPLE INC",
                "cusip": "037833100",  # Same CUSIP
                "value": 200000000,  # Different value
                "shares": 1000000000,
                "Company Name": "BERKSHIRE HATHAWAY INC",
                "CIK": "0001067983"  # Same CIK
            }
        ]
        
        result = normalize_13f(
            raw_data,
            source='sec_edgar',
            as_of=date(2023, 9, 30),
            ingested_at=datetime.now()
        )
        
        # Should deduplicate, keeping last
        assert len(result) == 1
        assert result[0]['value_usd'] == 200000000.0
