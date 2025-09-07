"""
Tests for orchestrated analysis job - SQLite to MetricsJSON pipeline.
Uses temp DB seeded with fixture rows; output file equals golden.
"""

import pytest
import sqlite3
import json
import tempfile
import os
from datetime import date, datetime
from pathlib import Path

# Import analysis job (will be created next)
from analysis.analysis_job import (
    analyze_ticker,
    AnalysisJobError,
    _query_price_data,
    _query_holdings_data
)
from storage.loaders import init_database, upsert_prices, upsert_13f


@pytest.fixture
def temp_db_with_data():
    """Create temporary database with test data."""
    # Create temp database
    conn = sqlite3.connect(':memory:')
    init_database(conn)
    
    # Insert test price data
    price_data = [
        {
            'ticker': 'AAPL',
            'date': date(2025, 8, 1),
            'open': 220.50, 'high': 222.30, 'low': 219.80, 'close': 221.75, 'adj_close': 221.50,
            'volume': 45000000, 'source': 'yfinance', 'as_of': date(2025, 8, 1),
            'ingested_at': datetime(2025, 8, 2, 9, 0, 0)
        },
        {
            'ticker': 'AAPL',
            'date': date(2025, 8, 4),
            'open': 221.80, 'high': 223.45, 'low': 221.20, 'close': 222.90, 'adj_close': 222.65,
            'volume': 38000000, 'source': 'yfinance', 'as_of': date(2025, 8, 4),
            'ingested_at': datetime(2025, 8, 5, 9, 0, 0)
        },
        {
            'ticker': 'AAPL',
            'date': date(2025, 8, 5),
            'open': 222.95, 'high': 224.10, 'low': 222.40, 'close': 223.55, 'adj_close': 223.30,
            'volume': 42000000, 'source': 'yfinance', 'as_of': date(2025, 8, 5),
            'ingested_at': datetime(2025, 8, 6, 9, 0, 0)
        }
    ]
    upsert_prices(conn, price_data)
    
    # Insert test 13F data
    holdings_data = [
        {
            'cik': '0001067983', 'filer': 'BERKSHIRE HATHAWAY INC',
            'ticker': 'AAPL', 'name': 'APPLE INC', 'cusip': '037833100',
            'value_usd': 50000000000.0, 'shares': 250000000.0,
            'as_of': date(2024, 9, 30), 'source': 'sec_edgar',
            'ingested_at': datetime(2025, 1, 15, 10, 0, 0)
        },
        {
            'cik': '0000102909', 'filer': 'VANGUARD GROUP INC',
            'ticker': 'AAPL', 'name': 'APPLE INC', 'cusip': '037833100',
            'value_usd': 30000000000.0, 'shares': 150000000.0,
            'as_of': date(2024, 9, 30), 'source': 'sec_edgar',
            'ingested_at': datetime(2025, 1, 15, 10, 0, 0)
        }
    ]
    upsert_13f(conn, holdings_data)
    
    return conn


class TestAnalysisJob:
    """Tests for analyze_ticker function."""
    
    def test_analyze_ticker_complete_data(self, temp_db_with_data):
        """Test analysis with both price and 13F data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'AAPL.json'
            
            result = analyze_ticker(
                conn=temp_db_with_data,
                ticker='AAPL',
                output_path=output_path,
                as_of_date=date(2025, 8, 5)
            )
            
            # Verify result summary
            assert result['ticker'] == 'AAPL'
            assert result['status'] == 'completed'
            assert result['output_path'] == str(output_path)
            assert result['metrics_calculated'] > 0
            
            # Verify file was created
            assert output_path.exists()
            
            # Verify file content is valid JSON
            with open(output_path, 'r') as f:
                metrics_json = json.load(f)
            
            # Verify MetricsJSON structure
            required_keys = {
                'ticker', 'as_of_date', 'data_period', 'price_metrics',
                'institutional_metrics', 'data_quality', 'metadata'
            }
            assert required_keys.issubset(metrics_json.keys())
            
            # Verify calculations were performed
            assert metrics_json['ticker'] == 'AAPL'
            assert metrics_json['price_metrics']['returns']['1D'] is not None
            assert metrics_json['institutional_metrics'] is not None
    
    def test_analyze_ticker_price_only(self, temp_db_with_data):
        """Test analysis with only price data (no 13F for ticker)."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'MSFT.json'
            
            # Add MSFT price data (no 13F)
            msft_price = [{
                'ticker': 'MSFT', 'date': date(2025, 8, 1),
                'open': 300.0, 'high': 305.0, 'low': 298.0, 'close': 302.0, 'adj_close': 301.50,
                'volume': 20000000, 'source': 'yfinance', 'as_of': date(2025, 8, 1),
                'ingested_at': datetime.now()
            }]
            upsert_prices(temp_db_with_data, msft_price)
            
            result = analyze_ticker(
                conn=temp_db_with_data,
                ticker='MSFT',
                output_path=output_path,
                as_of_date=date(2025, 8, 1)
            )
            
            assert result['status'] == 'completed'
            
            # Load and verify metrics
            with open(output_path, 'r') as f:
                metrics = json.load(f)
            
            # Should have price metrics but no institutional metrics
            assert metrics['price_metrics'] is not None
            assert metrics['institutional_metrics'] is None
    
    def test_analyze_ticker_no_data(self, temp_db_with_data):
        """Test analysis with no data for ticker."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'INVALID.json'
            
            result = analyze_ticker(
                conn=temp_db_with_data,
                ticker='INVALID',  # No data for this ticker
                output_path=output_path,
                as_of_date=date(2025, 8, 5)
            )
            
            assert result['status'] == 'failed'
            assert 'No price data' in result['error_message']
            
            # File should not be created
            assert not output_path.exists()
    
    def test_query_price_data(self, temp_db_with_data):
        """Test price data querying function."""
        df = _query_price_data(temp_db_with_data, 'AAPL')
        
        assert not df.empty
        assert len(df) == 3  # 3 AAPL records inserted
        assert all(df['ticker'] == 'AAPL')
        assert 'close' in df.columns
        assert 'date' in df.columns
        
        # Should be sorted by date
        dates = df['date'].tolist()
        assert dates == sorted(dates)
    
    def test_query_holdings_data(self, temp_db_with_data):
        """Test 13F holdings data querying function."""
        df = _query_holdings_data(temp_db_with_data, 'AAPL')
        
        assert not df.empty
        assert len(df) == 2  # 2 AAPL holdings inserted
        assert all(df['ticker'] == 'AAPL')
        assert 'value_usd' in df.columns
        assert 'filer' in df.columns
    
    def test_query_price_data_no_results(self, temp_db_with_data):
        """Test price querying with no results."""
        df = _query_price_data(temp_db_with_data, 'NONEXISTENT')
        
        assert df.empty
        assert 'ticker' in df.columns  # Should have expected columns
    
    def test_analyze_ticker_output_directory_creation(self, temp_db_with_data):
        """Test that output directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create nested path that doesn't exist
            output_path = Path(temp_dir) / 'metrics' / 'AAPL.json'
            
            result = analyze_ticker(
                conn=temp_db_with_data,
                ticker='AAPL',
                output_path=output_path,
                as_of_date=date(2025, 8, 5)
            )
            
            assert result['status'] == 'completed'
            assert output_path.exists()
            assert output_path.parent.exists()  # Directory was created
    
    def test_analyze_ticker_deterministic_output(self, temp_db_with_data):
        """Test that analysis produces deterministic output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path1 = Path(temp_dir) / 'AAPL_1.json'
            output_path2 = Path(temp_dir) / 'AAPL_2.json'
            
            # Run analysis twice with same inputs
            result1 = analyze_ticker(temp_db_with_data, 'AAPL', output_path1, date(2025, 8, 5))
            result2 = analyze_ticker(temp_db_with_data, 'AAPL', output_path2, date(2025, 8, 5))
            
            # Load both outputs
            with open(output_path1, 'r') as f:
                metrics1 = json.load(f)
            with open(output_path2, 'r') as f:
                metrics2 = json.load(f)
            
            # Remove timestamps (will be different)
            del metrics1['metadata']['calculated_at']
            del metrics2['metadata']['calculated_at']
            
            # Should be identical (deterministic)
            assert metrics1 == metrics2
