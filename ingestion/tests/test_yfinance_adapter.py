"""
Tests for yfinance adapter - mocked network calls, no live API hits in CI.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import date, datetime
import pandas as pd

# Import adapter (will be created next)
from ingestion.providers.yfinance_adapter import (
    fetch_prices_window,
    YFinanceError,
    _validate_date_range
)


class TestYFinanceAdapter:
    """Tests for fetch_prices_window function."""
    
    @patch('ingestion.providers.yfinance_adapter.yf.download')
    def test_fetch_prices_window_success(self, mock_download):
        """Test successful price fetch with mocked yfinance."""
        # Mock yfinance response
        mock_data = pd.DataFrame({
            'Open': [185.25, 186.10],
            'High': [186.80, 187.45],
            'Low': [184.50, 185.80],
            'Close': [185.92, 187.11],
            'Adj Close': [185.75, 186.94],
            'Volume': [65284300, 58414500]
        }, index=pd.DatetimeIndex(['2024-01-15', '2024-01-16'], name='Date'))
        
        mock_download.return_value = mock_data
        
        # Call adapter
        result = fetch_prices_window(
            ticker='AAPL',
            start=date(2024, 1, 15),
            end=date(2024, 1, 16)
        )
        
        # Verify yfinance was called correctly
        mock_download.assert_called_once_with(
            'AAPL',
            start='2024-01-15',
            end='2024-01-17',  # yfinance end is exclusive
            progress=False,
            show_errors=False
        )
        
        # Verify result structure
        assert len(result) == 2
        assert result[0]['Date'] == '2024-01-15'
        assert result[0]['Open'] == 185.25
        assert result[0]['Volume'] == 65284300
        
        assert result[1]['Date'] == '2024-01-16'
        assert result[1]['Close'] == 187.11
    
    @patch('ingestion.providers.yfinance_adapter.yf.download')
    def test_fetch_prices_window_empty_response(self, mock_download):
        """Test handling of empty yfinance response."""
        # Mock empty DataFrame
        mock_download.return_value = pd.DataFrame()
        
        result = fetch_prices_window(
            ticker='INVALID',
            start=date(2024, 1, 15),
            end=date(2024, 1, 16)
        )
        
        assert result == []
    
    @patch('ingestion.providers.yfinance_adapter.yf.download')
    def test_fetch_prices_window_network_error(self, mock_download):
        """Test handling of network errors."""
        # Mock network exception
        mock_download.side_effect = Exception("Network timeout")
        
        with pytest.raises(YFinanceError, match="Failed to fetch.*Network timeout"):
            fetch_prices_window(
                ticker='AAPL',
                start=date(2024, 1, 15),
                end=date(2024, 1, 16)
            )
    
    @patch('ingestion.providers.yfinance_adapter.yf.download')
    def test_fetch_prices_window_partial_data(self, mock_download):
        """Test handling of partial data (some missing fields)."""
        # Mock DataFrame with missing Adj Close
        mock_data = pd.DataFrame({
            'Open': [185.25],
            'High': [186.80],
            'Low': [184.50],
            'Close': [185.92],
            # No 'Adj Close'
            'Volume': [65284300]
        }, index=pd.DatetimeIndex(['2024-01-15'], name='Date'))
        
        mock_download.return_value = mock_data
        
        result = fetch_prices_window(
            ticker='AAPL',
            start=date(2024, 1, 15),
            end=date(2024, 1, 15)
        )
        
        assert len(result) == 1
        assert 'Adj Close' not in result[0]  # Should not include missing fields
        assert result[0]['Open'] == 185.25
    
    def test_validate_date_range_valid(self):
        """Test date range validation with valid range."""
        # Should not raise
        _validate_date_range(
            start=date(2024, 1, 15),
            end=date(2024, 1, 16)
        )
    
    def test_validate_date_range_invalid_order(self):
        """Test date range validation with end before start."""
        with pytest.raises(YFinanceError, match="start.*must be <= end"):
            _validate_date_range(
                start=date(2024, 1, 16),
                end=date(2024, 1, 15)
            )
    
    def test_validate_date_range_future_dates(self):
        """Test date range validation with future dates."""
        future_date = date(2030, 1, 1)
        with pytest.raises(YFinanceError, match="Future dates not allowed"):
            _validate_date_range(
                start=future_date,
                end=future_date
            )
    
    def test_validate_date_range_too_long(self):
        """Test date range validation with excessive range."""
        with pytest.raises(YFinanceError, match="Date range too long"):
            _validate_date_range(
                start=date(2020, 1, 1),
                end=date(2024, 1, 1)  # > 3 years
            )
    
    @patch('ingestion.providers.yfinance_adapter.yf.download')
    def test_fetch_prices_window_preserves_order(self, mock_download):
        """Test that date order is preserved from yfinance."""
        # Mock data in chronological order
        mock_data = pd.DataFrame({
            'Open': [100.0, 101.0, 102.0],
            'High': [101.0, 102.0, 103.0],
            'Low': [99.0, 100.0, 101.0],
            'Close': [100.5, 101.5, 102.5],
            'Volume': [1000000, 1100000, 1200000]
        }, index=pd.DatetimeIndex(['2024-01-15', '2024-01-16', '2024-01-17'], name='Date'))
        
        mock_download.return_value = mock_data
        
        result = fetch_prices_window(
            ticker='TEST',
            start=date(2024, 1, 15),
            end=date(2024, 1, 17)
        )
        
        # Verify chronological order preserved
        dates = [row['Date'] for row in result]
        assert dates == ['2024-01-15', '2024-01-16', '2024-01-17']
        
        # Verify values match
        assert result[0]['Close'] == 100.5
        assert result[1]['Close'] == 101.5
        assert result[2]['Close'] == 102.5
    
    @patch('ingestion.providers.yfinance_adapter.yf.download')
    def test_fetch_prices_window_single_day(self, mock_download):
        """Test fetching single day of data."""
        mock_data = pd.DataFrame({
            'Open': [185.25],
            'High': [186.80],
            'Low': [184.50],
            'Close': [185.92],
            'Adj Close': [185.75],
            'Volume': [65284300]
        }, index=pd.DatetimeIndex(['2024-01-15'], name='Date'))
        
        mock_download.return_value = mock_data
        
        result = fetch_prices_window(
            ticker='AAPL',
            start=date(2024, 1, 15),
            end=date(2024, 1, 15)  # Same day
        )
        
        assert len(result) == 1
        assert result[0]['Date'] == '2024-01-15'
        
        # Verify yfinance called with correct dates
        mock_download.assert_called_once_with(
            'AAPL',
            start='2024-01-15',
            end='2024-01-16',  # Next day (exclusive)
            progress=False,
            show_errors=False
        )
