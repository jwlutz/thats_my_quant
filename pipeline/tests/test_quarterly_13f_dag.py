"""
Tests for quarterly_13f DAG - integration test of 13F holdings pipeline.
Uses mocked 13F adapter but real transforms and storage.
"""

import pytest
import sqlite3
from unittest.mock import Mock, patch
from datetime import date, datetime
import os

# Import DAG (will be created next)
from pipeline.quarterly_13f_dag import (
    run_quarterly_13f,
    Quarterly13FConfig,
    PipelineError
)
from storage.loaders import init_database


@pytest.fixture
def in_memory_db():
    """Create in-memory SQLite database for testing."""
    conn = sqlite3.connect(':memory:')
    init_database(conn)
    return conn


class TestQuarterly13FDAG:
    """Tests for quarterly_13f DAG orchestration."""
    
    @patch.dict(os.environ, {'SEC_USER_AGENT': 'Test User test@example.com'})
    @patch('pipeline.quarterly_13f_dag.fetch_13f_quarter')
    def test_run_quarterly_13f_success(self, mock_fetch, in_memory_db):
        """Test successful end-to-end quarterly 13F pipeline."""
        # Mock 13F data (format from existing scraper)
        mock_fetch.return_value = [
            {
                'Company Name': 'BERKSHIRE HATHAWAY INC',
                'CIK': '0001067983',
                'nameOfIssuer': 'APPLE INC',
                'cusip': '037833100',
                'value': 174800000,  # In thousands (SEC format)
                'shares': 915560382,
                'shareType': 'SH',
                'putCall': None,
                'filing_date': '2025-02-14'
            },
            {
                'Company Name': 'BERKSHIRE HATHAWAY INC',
                'CIK': '0001067983',
                'nameOfIssuer': 'BANK OF AMERICA CORP',
                'cusip': '060505104',
                'value': 28280000,
                'shares': 1032852006,
                'shareType': 'SH',
                'putCall': None,
                'filing_date': '2025-02-14'
            }
        ]
        
        # Configure pipeline
        config = Quarterly13FConfig(
            entity_name='BERKSHIRE HATHAWAY INC',
            quarter_end=date(2024, 12, 31)  # Q4 2024
        )
        
        # Run pipeline
        result = run_quarterly_13f(config, conn=in_memory_db)
        
        # Verify adapter was called correctly
        mock_fetch.assert_called_once_with(
            entity_name='BERKSHIRE HATHAWAY INC',
            quarter_end=date(2024, 12, 31)
        )
        
        # Verify result structure
        assert result['status'] == 'completed'
        assert result['entity_name'] == 'BERKSHIRE HATHAWAY INC'
        assert result['quarter_end'] == date(2024, 12, 31)
        assert result['rows_fetched'] == 2
        assert result['rows_stored'] == 2
        assert result['run_id'] is not None
        assert result['duration_seconds'] is not None
        
        # Verify data in database
        cursor = in_memory_db.execute(
            "SELECT COUNT(*) FROM holdings_13f WHERE cik = '0001067983'"
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
        assert run_record[1] == 2
        assert run_record[2] == 2
    
    @patch.dict(os.environ, {'SEC_USER_AGENT': 'Test User test@example.com'})
    @patch('pipeline.quarterly_13f_dag.fetch_13f_quarter')
    def test_run_quarterly_13f_empty_data(self, mock_fetch, in_memory_db):
        """Test pipeline with empty 13F data."""
        mock_fetch.return_value = []
        
        config = Quarterly13FConfig(
            entity_name='SMALL FUND',
            quarter_end=date(2024, 12, 31)
        )
        
        result = run_quarterly_13f(config, conn=in_memory_db)
        
        assert result['status'] == 'completed'
        assert result['rows_fetched'] == 0
        assert result['rows_stored'] == 0
        
        # No data should be in database
        cursor = in_memory_db.execute(
            "SELECT COUNT(*) FROM holdings_13f"
        )
        count = cursor.fetchone()[0]
        assert count == 0
    
    @patch.dict(os.environ, {'SEC_USER_AGENT': 'Test User test@example.com'})
    @patch('pipeline.quarterly_13f_dag.fetch_13f_quarter')
    def test_run_quarterly_13f_provider_failure(self, mock_fetch, in_memory_db):
        """Test pipeline when 13F provider fails."""
        mock_fetch.side_effect = Exception("CIK not found")
        
        config = Quarterly13FConfig(
            entity_name='INVALID COMPANY',
            quarter_end=date(2024, 12, 31)
        )
        
        result = run_quarterly_13f(config, conn=in_memory_db)
        
        assert result['status'] == 'failed'
        assert 'CIK not found' in result['error_message']
        assert result['rows_fetched'] == 0
        assert result['rows_stored'] == 0
        
        # Run should be marked as failed
        cursor = in_memory_db.execute(
            "SELECT status FROM runs WHERE run_id = ?",
            (result['run_id'],)
        )
        status = cursor.fetchone()[0]
        assert status == 'failed'
    
    @patch.dict(os.environ, {'SEC_USER_AGENT': 'Test User test@example.com'})
    @patch('pipeline.quarterly_13f_dag.fetch_13f_quarter')
    def test_run_quarterly_13f_by_cik(self, mock_fetch, in_memory_db):
        """Test running pipeline with CIK instead of entity name."""
        mock_fetch.return_value = [
            {
                'Company Name': 'BERKSHIRE HATHAWAY INC',
                'CIK': '0001067983',
                'nameOfIssuer': 'APPLE INC',
                'cusip': '037833100',
                'value': 174800000,
                'shares': 915560382,
                'filing_date': '2025-02-14'
            }
        ]
        
        config = Quarterly13FConfig(
            cik='0001067983',
            quarter_end=date(2024, 12, 31)
        )
        
        result = run_quarterly_13f(config, conn=in_memory_db)
        
        # Verify adapter called with CIK
        mock_fetch.assert_called_once_with(
            cik='0001067983',
            quarter_end=date(2024, 12, 31)
        )
        
        assert result['status'] == 'completed'
        assert result['cik'] == '0001067983'
        assert result['rows_stored'] == 1
    
    @patch.dict(os.environ, {'SEC_USER_AGENT': 'Test User test@example.com'})
    @patch('pipeline.quarterly_13f_dag.fetch_13f_quarter')
    def test_run_quarterly_13f_validation_failure(self, mock_fetch, in_memory_db):
        """Test pipeline when 13F data validation fails."""
        # Mock invalid data (negative shares)
        mock_fetch.return_value = [
            {
                'Company Name': 'TEST COMPANY',
                'CIK': '0000000001',
                'nameOfIssuer': 'INVALID STOCK',
                'cusip': '123456789',
                'value': 1000000,
                'shares': -100,  # Invalid: negative shares
                'filing_date': '2025-02-14'
            }
        ]
        
        config = Quarterly13FConfig(
            entity_name='TEST COMPANY',
            quarter_end=date(2024, 12, 31)
        )
        
        result = run_quarterly_13f(config, conn=in_memory_db)
        
        assert result['status'] == 'failed'
        assert 'validation' in result['error_message'].lower()
        assert result['rows_fetched'] == 1
        assert result['rows_stored'] == 0  # Should not store invalid data
    
    def test_quarterly_13f_config_validation(self):
        """Test configuration validation."""
        # Valid config with entity name
        config = Quarterly13FConfig(
            entity_name='BERKSHIRE HATHAWAY INC',
            quarter_end=date(2024, 12, 31)
        )
        assert config.entity_name == 'BERKSHIRE HATHAWAY INC'
        assert config.quarter_end == date(2024, 12, 31)
        
        # Valid config with CIK
        config_cik = Quarterly13FConfig(
            cik='0001067983',
            quarter_end=date(2024, 12, 31)
        )
        assert config_cik.cik == '0001067983'
        
        # Invalid: neither entity_name nor cik
        with pytest.raises(ValueError, match="Must provide either entity_name or cik"):
            Quarterly13FConfig(quarter_end=date(2024, 12, 31))
        
        # Invalid: both entity_name and cik
        with pytest.raises(ValueError, match="Provide either entity_name or cik, not both"):
            Quarterly13FConfig(
                entity_name='TEST',
                cik='0000000001',
                quarter_end=date(2024, 12, 31)
            )
        
        # Invalid quarter end
        with pytest.raises(ValueError, match="Invalid quarter end"):
            Quarterly13FConfig(
                entity_name='TEST',
                quarter_end=date(2024, 4, 15)  # Not a quarter end
            )
    
    @patch.dict(os.environ, {'SEC_USER_AGENT': 'Test User test@example.com'})
    @patch('pipeline.quarterly_13f_dag.fetch_13f_quarter')
    def test_run_quarterly_13f_idempotent(self, mock_fetch, in_memory_db):
        """Test that running 13F pipeline twice is idempotent."""
        mock_fetch.return_value = [
            {
                'Company Name': 'BERKSHIRE HATHAWAY INC',
                'CIK': '0001067983',
                'nameOfIssuer': 'APPLE INC',
                'cusip': '037833100',
                'value': 174800000,
                'shares': 915560382,
                'filing_date': '2025-02-14'
            }
        ]
        
        config = Quarterly13FConfig(
            entity_name='BERKSHIRE HATHAWAY INC',
            quarter_end=date(2024, 12, 31)
        )
        
        # First run
        result1 = run_quarterly_13f(config, conn=in_memory_db)
        
        # Second run with same data
        result2 = run_quarterly_13f(config, conn=in_memory_db)
        
        # Both should succeed
        assert result1['status'] == 'completed'
        assert result2['status'] == 'completed'
        
        # Should still only have one row in database (idempotent)
        cursor = in_memory_db.execute(
            "SELECT COUNT(*) FROM holdings_13f WHERE cik = '0001067983' AND cusip = '037833100'"
        )
        count = cursor.fetchone()[0]
        assert count == 1
    
    @patch.dict(os.environ, {'SEC_USER_AGENT': 'Test User test@example.com'})
    @patch('pipeline.quarterly_13f_dag.fetch_13f_quarter')
    def test_run_quarterly_13f_metrics_calculation(self, mock_fetch, in_memory_db):
        """Test that pipeline calculates correct 13F metrics."""
        mock_fetch.return_value = [
            {
                'Company Name': 'BERKSHIRE HATHAWAY INC',
                'CIK': '0001067983',
                'nameOfIssuer': 'APPLE INC',
                'cusip': '037833100',
                'value': 174800000,  # $174.8B in thousands
                'shares': 915560382,
                'filing_date': '2025-02-14'
            },
            {
                'Company Name': 'BERKSHIRE HATHAWAY INC',
                'CIK': '0001067983',
                'nameOfIssuer': 'BANK OF AMERICA CORP',
                'cusip': '060505104',
                'value': 28280000,   # $28.3B in thousands
                'shares': 1032852006,
                'filing_date': '2025-02-14'
            }
        ]
        
        config = Quarterly13FConfig(
            entity_name='BERKSHIRE HATHAWAY INC',
            quarter_end=date(2024, 12, 31)
        )
        
        result = run_quarterly_13f(config, conn=in_memory_db)
        
        assert result['status'] == 'completed'
        assert result['rows_stored'] == 2
        
        # Check computed metrics
        assert 'holdings_summary' in result
        summary = result['holdings_summary']
        assert summary['total_positions'] == 2
        assert summary['total_value_usd'] > 200000000000  # > $200B
        assert summary['largest_position']['ticker'] == 'AAPL'  # Apple should be largest
        assert summary['largest_position']['value_usd'] == 174800000000.0
