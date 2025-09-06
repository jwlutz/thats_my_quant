"""
Tests for daily_prices DAG - integration test of full pipeline.
Uses mocked providers but real transforms and storage.
"""

import pytest
import sqlite3
from unittest.mock import Mock, patch
from datetime import date, datetime, timedelta
import pandas as pd

# Import DAG (will be created next)
from pipeline.daily_prices_dag import (
    run_daily_prices,
    DailyPricesConfig,
    PipelineError
)
from storage.loaders import init_database


@pytest.fixture
def in_memory_db():
    """Create in-memory SQLite database for testing."""
    conn = sqlite3.connect(':memory:')
    init_database(conn)
    return conn


class TestDailyPricesDAG:
    """Tests for daily_prices DAG orchestration."""
    
    @patch('pipeline.daily_prices_dag.fetch_prices_window')
    def test_run_daily_prices_success(self, mock_fetch, in_memory_db):
        """Test successful end-to-end daily prices pipeline."""
        # Mock yfinance data
        mock_fetch.return_value = [
            {
                'Date': '2024-01-15',
                'Open': 185.25,
                'High': 186.80,
                'Low': 184.50,
                'Close': 185.92,
                'Adj Close': 185.75,
                'Volume': 65284300
            },
            {
                'Date': '2024-01-16', 
                'Open': 186.10,
                'High': 187.45,
                'Low': 185.80,
                'Close': 187.11,
                'Adj Close': 186.94,
                'Volume': 58414500
            }
        ]
        
        # Configure pipeline
        config = DailyPricesConfig(
            ticker='AAPL',
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 16)
        )
        
        # Run pipeline
        result = run_daily_prices(config, conn=in_memory_db)
        
        # Verify provider was called correctly
        mock_fetch.assert_called_once_with(
            ticker='AAPL',
            start=date(2024, 1, 15),
            end=date(2024, 1, 16)
        )
        
        # Verify result structure
        assert result['status'] == 'completed'
        assert result['ticker'] == 'AAPL'
        assert result['rows_fetched'] == 2
        assert result['rows_stored'] == 2
        assert result['run_id'] is not None
        assert result['duration_seconds'] is not None
        
        # Verify data in database
        cursor = in_memory_db.execute(
            "SELECT COUNT(*) FROM prices WHERE ticker = 'AAPL'"
        )
        count = cursor.fetchone()[0]
        assert count == 2
        
        # Verify run was tracked
        cursor = in_memory_db.execute(
            "SELECT status, rows_in, rows_out FROM runs WHERE run_id = ?",
            (result['run_id'],)
        )
        run_record = cursor.fetchone()
        assert run_record[0] == 'completed'
        assert run_record[1] == 2  # rows_in
        assert run_record[2] == 2  # rows_out
    
    @patch('pipeline.daily_prices_dag.fetch_prices_window')
    def test_run_daily_prices_empty_data(self, mock_fetch, in_memory_db):
        """Test pipeline with empty data from provider."""
        mock_fetch.return_value = []
        
        config = DailyPricesConfig(
            ticker='INVALID',
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 16)
        )
        
        result = run_daily_prices(config, conn=in_memory_db)
        
        assert result['status'] == 'completed'
        assert result['rows_fetched'] == 0
        assert result['rows_stored'] == 0
        
        # No data should be in database
        cursor = in_memory_db.execute(
            "SELECT COUNT(*) FROM prices WHERE ticker = 'INVALID'"
        )
        count = cursor.fetchone()[0]
        assert count == 0
    
    @patch('pipeline.daily_prices_dag.fetch_prices_window')
    def test_run_daily_prices_provider_failure(self, mock_fetch, in_memory_db):
        """Test pipeline when provider fails."""
        mock_fetch.side_effect = Exception("Network timeout")
        
        config = DailyPricesConfig(
            ticker='AAPL',
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 16)
        )
        
        result = run_daily_prices(config, conn=in_memory_db)
        
        assert result['status'] == 'failed'
        assert 'Network timeout' in result['error_message']
        assert result['rows_fetched'] == 0
        assert result['rows_stored'] == 0
        
        # Run should be marked as failed
        cursor = in_memory_db.execute(
            "SELECT status FROM runs WHERE run_id = ?",
            (result['run_id'],)
        )
        status = cursor.fetchone()[0]
        assert status == 'failed'
    
    @patch('pipeline.daily_prices_dag.fetch_prices_window')
    def test_run_daily_prices_validation_failure(self, mock_fetch, in_memory_db):
        """Test pipeline when data validation fails."""
        # Mock invalid data (high < low)
        mock_fetch.return_value = [
            {
                'Date': '2024-01-15',
                'Open': 185.25,
                'High': 180.00,  # Invalid: high < low
                'Low': 186.00,
                'Close': 185.92,
                'Volume': 65284300
            }
        ]
        
        config = DailyPricesConfig(
            ticker='AAPL',
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 15)
        )
        
        result = run_daily_prices(config, conn=in_memory_db)
        
        assert result['status'] == 'failed'
        assert 'validation' in result['error_message'].lower()
        assert result['rows_fetched'] == 1
        assert result['rows_stored'] == 0  # Should not store invalid data
    
    @patch('pipeline.daily_prices_dag.fetch_prices_window')
    def test_run_daily_prices_partial_validation_failure(self, mock_fetch, in_memory_db):
        """Test pipeline when some rows fail validation."""
        mock_fetch.return_value = [
            {
                'Date': '2024-01-15',
                'Open': 185.25,
                'High': 186.80,
                'Low': 184.50,
                'Close': 185.92,
                'Volume': 65284300
            },
            {
                'Date': '2024-01-16',
                'Open': 186.10,
                'High': 180.00,  # Invalid: high < low
                'Low': 186.00,
                'Close': 187.11,
                'Volume': 58414500
            }
        ]
        
        config = DailyPricesConfig(
            ticker='AAPL',
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 16)
        )
        
        result = run_daily_prices(config, conn=in_memory_db)
        
        # Should complete but with warnings
        assert result['status'] == 'completed'
        assert result['rows_fetched'] == 2
        assert result['rows_stored'] == 1  # Only valid row stored
        assert 'validation_warnings' in result
        assert result['validation_warnings'] == 1
    
    def test_daily_prices_config_validation(self):
        """Test configuration validation."""
        # Valid config
        config = DailyPricesConfig(
            ticker='AAPL',
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 16)
        )
        assert config.ticker == 'AAPL'
        assert config.days_range == 1
        
        # Invalid date range
        with pytest.raises(ValueError, match="start_date.*end_date"):
            DailyPricesConfig(
                ticker='AAPL',
                start_date=date(2024, 1, 16),
                end_date=date(2024, 1, 15)  # end before start
            )
        
        # Invalid ticker
        with pytest.raises(ValueError, match="ticker.*empty"):
            DailyPricesConfig(
                ticker='',
                start_date=date(2024, 1, 15),
                end_date=date(2024, 1, 16)
            )
    
    def test_daily_prices_config_defaults(self):
        """Test configuration default values."""
        # Default date range (last 365 days)
        config = DailyPricesConfig(ticker='AAPL')
        
        assert config.ticker == 'AAPL'
        assert config.end_date == date.today()
        assert config.start_date == date.today() - timedelta(days=365)
        assert config.days_range == 365
    
    @patch('pipeline.daily_prices_dag.fetch_prices_window')
    def test_run_daily_prices_idempotent(self, mock_fetch, in_memory_db):
        """Test that running pipeline twice with same data is idempotent."""
        mock_fetch.return_value = [
            {
                'Date': '2024-01-15',
                'Open': 185.25,
                'High': 186.80,
                'Low': 184.50,
                'Close': 185.92,
                'Volume': 65284300
            }
        ]
        
        config = DailyPricesConfig(
            ticker='AAPL',
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 15)
        )
        
        # First run
        result1 = run_daily_prices(config, conn=in_memory_db)
        
        # Second run with same data
        result2 = run_daily_prices(config, conn=in_memory_db)
        
        # Both should succeed
        assert result1['status'] == 'completed'
        assert result2['status'] == 'completed'
        
        # First run inserts, second run updates
        assert result1['rows_stored'] == 1
        assert result2['rows_stored'] == 1  # Still reports 1 row processed
        
        # Should still only have one row in database
        cursor = in_memory_db.execute(
            "SELECT COUNT(*) FROM prices WHERE ticker = 'AAPL'"
        )
        count = cursor.fetchone()[0]
        assert count == 1
    
    @patch('pipeline.daily_prices_dag.fetch_prices_window')
    def test_run_daily_prices_metrics_calculation(self, mock_fetch, in_memory_db):
        """Test that pipeline calculates correct metrics."""
        mock_fetch.return_value = [
            {'Date': '2024-01-15', 'Open': 100.0, 'High': 101.0, 'Low': 99.0, 'Close': 100.5, 'Volume': 1000},
            {'Date': '2024-01-16', 'Open': 100.5, 'High': 102.0, 'Low': 100.0, 'Close': 101.5, 'Volume': 1200},
            {'Date': '2024-01-17', 'Open': 101.5, 'High': 103.0, 'Low': 101.0, 'Close': 102.0, 'Volume': 800}
        ]
        
        config = DailyPricesConfig(
            ticker='TEST',
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 17)
        )
        
        result = run_daily_prices(config, conn=in_memory_db)
        
        assert result['status'] == 'completed'
        assert result['rows_fetched'] == 3
        assert result['rows_stored'] == 3
        
        # Check computed metrics
        assert 'price_range' in result
        assert result['price_range']['min_close'] == 100.5
        assert result['price_range']['max_close'] == 102.0
        assert result['total_volume'] == 3000  # 1000 + 1200 + 800
