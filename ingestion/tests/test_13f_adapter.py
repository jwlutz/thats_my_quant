"""
Tests for 13F adapter - wrapper around existing data_extraction.py.
Uses fixtures to mock the scraper's output.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import date, datetime
import pandas as pd
import os

# Import adapter (will be created next)
from ingestion.providers.sec_13f_adapter import (
    fetch_13f_quarter,
    SEC13FError,
    _validate_quarter_end,
    _configure_scraper_env
)


class TestSEC13FAdapter:
    """Tests for fetch_13f_quarter function."""
    
    @patch.dict(os.environ, {'SEC_USER_AGENT': 'Test User test@example.com'})
    @patch('ingestion.providers.sec_13f_adapter.download_13f_in_date_range')
    def test_fetch_13f_quarter_success(self, mock_download):
        """Test successful 13F fetch with mocked scraper."""
        # Mock scraper response (DataFrame)
        mock_df = pd.DataFrame([
            {
                'Company Name': 'BERKSHIRE HATHAWAY INC',
                'CIK': '0001067983',
                'nameOfIssuer': 'APPLE INC',
                'cusip': '037833100',
                'value': 174800000,  # In thousands
                'shares': 915560382,
                'shareType': 'SH',
                'putCall': None,
                'filing_date': '2023-11-14',
                'filing_url': 'https://www.sec.gov/Archives/edgar/data/1067983/000095017023061398/xslForm13F_X01/form13fInfoTable.xml'
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
                'filing_date': '2023-11-14',
                'filing_url': 'https://www.sec.gov/Archives/edgar/data/1067983/000095017023061398/xslForm13F_X01/form13fInfoTable.xml'
            }
        ])
        
        mock_download.return_value = mock_df
        
        # Call adapter
        result = fetch_13f_quarter(
            entity_name='BERKSHIRE HATHAWAY INC',
            quarter_end=date(2023, 9, 30)
        )
        
        # Verify scraper was called correctly
        mock_download.assert_called_once_with(
            start_date='2023-07-01',  # Q3 start
            end_date='2023-12-31',    # Filing deadline
            entity_name='BERKSHIRE HATHAWAY INC',
            save=False
        )
        
        # Verify result structure (raw format from scraper)
        assert len(result) == 2
        assert result[0]['Company Name'] == 'BERKSHIRE HATHAWAY INC'
        assert result[0]['nameOfIssuer'] == 'APPLE INC'
        assert result[0]['cusip'] == '037833100'
        assert result[0]['value'] == 174800000
        
        assert result[1]['nameOfIssuer'] == 'BANK OF AMERICA CORP'
        assert result[1]['cusip'] == '060505104'
    
    @patch.dict(os.environ, {'SEC_USER_AGENT': 'Test User test@example.com'})
    @patch('ingestion.providers.sec_13f_adapter.download_13f_in_date_range')
    def test_fetch_13f_quarter_empty_response(self, mock_download):
        """Test handling of empty scraper response."""
        # Mock empty DataFrame
        mock_download.return_value = pd.DataFrame()
        
        result = fetch_13f_quarter(
            entity_name='UNKNOWN COMPANY',
            quarter_end=date(2023, 9, 30)
        )
        
        assert result == []
    
    @patch.dict(os.environ, {'SEC_USER_AGENT': 'Test User test@example.com'})
    @patch('ingestion.providers.sec_13f_adapter.download_13f_in_date_range')
    def test_fetch_13f_quarter_scraper_error(self, mock_download):
        """Test handling of scraper errors."""
        # Mock scraper exception
        mock_download.side_effect = Exception("CIK not found")
        
        with pytest.raises(SEC13FError, match="Failed to fetch 13F.*CIK not found"):
            fetch_13f_quarter(
                entity_name='INVALID COMPANY',
                quarter_end=date(2023, 9, 30)
            )
    
    @patch.dict(os.environ, {'SEC_USER_AGENT': 'Test User test@example.com'})
    @patch('ingestion.providers.sec_13f_adapter.download_13f_in_date_range')
    def test_fetch_13f_quarter_by_cik(self, mock_download):
        """Test fetching by CIK instead of entity name."""
        mock_df = pd.DataFrame([
            {
                'Company Name': 'BERKSHIRE HATHAWAY INC',
                'CIK': '0001067983',
                'nameOfIssuer': 'APPLE INC',
                'cusip': '037833100',
                'value': 174800000,
                'shares': 915560382,
                'filing_date': '2023-11-14'
            }
        ])
        
        mock_download.return_value = mock_df
        
        # Call with CIK
        result = fetch_13f_quarter(
            cik='0001067983',
            quarter_end=date(2023, 9, 30)
        )
        
        # Should pass data dict to scraper instead of entity_name
        expected_data = {'CIK': '0001067983'}
        mock_download.assert_called_once_with(
            start_date='2023-07-01',
            end_date='2023-12-31',
            entity_name=None,
            save=False,
            data=expected_data
        )
        
        assert len(result) == 1
        assert result[0]['CIK'] == '0001067983'
    
    def test_validate_quarter_end_valid(self):
        """Test quarter end validation with valid dates."""
        # Valid quarter ends
        valid_dates = [
            date(2023, 3, 31),   # Q1
            date(2023, 6, 30),   # Q2
            date(2023, 9, 30),   # Q3
            date(2023, 12, 31),  # Q4
        ]
        
        for qdate in valid_dates:
            # Should not raise
            _validate_quarter_end(qdate)
    
    def test_validate_quarter_end_invalid(self):
        """Test quarter end validation with invalid dates."""
        invalid_dates = [
            date(2023, 3, 30),   # Not end of quarter
            date(2023, 6, 29),   # Not end of quarter
            date(2023, 4, 30),   # Not a quarter end month
            date(2030, 3, 31),   # Future date
        ]
        
        for qdate in invalid_dates:
            with pytest.raises(SEC13FError):
                _validate_quarter_end(qdate)
    
    def test_validate_quarter_end_too_old(self):
        """Test validation rejects very old dates."""
        old_date = date(2010, 3, 31)  # Too old
        with pytest.raises(SEC13FError, match="Quarter end too old"):
            _validate_quarter_end(old_date)
    
    @patch.dict(os.environ, {
        'SEC_USER_AGENT': 'Test User test@example.com',
        'SEC_CONTACT_EMAIL': 'test@example.com',
        'SEC_RATE_LIMIT_RPS': '3'
    })
    @patch('ingestion.providers.sec_13f_adapter.data_extraction')
    def test_configure_scraper_env(self, mock_data_extraction):
        """Test that environment variables are applied to scraper."""
        # Mock the data_extraction module
        mock_data_extraction.HEADERS = {}
        mock_data_extraction.RATE_LIMITER = Mock()
        
        _configure_scraper_env()
        
        # Verify headers were updated
        assert mock_data_extraction.HEADERS['User-Agent'] == 'Test User test@example.com'
        
        # Verify rate limiter was updated
        mock_data_extraction.RATE_LIMITER.max_calls = 3
        mock_data_extraction.RATE_LIMITER.period = 1.0
    
    def test_configure_scraper_env_missing_required(self):
        """Test that missing required env vars raise error."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SEC13FError, match="SEC_USER_AGENT.*required"):
                _configure_scraper_env()
    
    @patch.dict(os.environ, {'SEC_USER_AGENT': 'Test User test@example.com'})
    @patch('ingestion.providers.sec_13f_adapter.download_13f_in_date_range')
    def test_fetch_13f_quarter_date_range_mapping(self, mock_download):
        """Test correct date range mapping for different quarters."""
        mock_download.return_value = pd.DataFrame()
        
        # Test Q1
        fetch_13f_quarter(
            entity_name='TEST',
            quarter_end=date(2023, 3, 31)
        )
        mock_download.assert_called_with(
            start_date='2023-01-01',  # Q1 start
            end_date='2023-06-30',    # Q1 filing deadline
            entity_name='TEST',
            save=False
        )
        
        # Test Q4
        mock_download.reset_mock()
        fetch_13f_quarter(
            entity_name='TEST',
            quarter_end=date(2023, 12, 31)
        )
        mock_download.assert_called_with(
            start_date='2023-10-01',  # Q4 start
            end_date='2024-03-31',    # Q4 filing deadline (next year)
            entity_name='TEST',
            save=False
        )
    
    @patch.dict(os.environ, {'SEC_USER_AGENT': 'Test User test@example.com'})
    @patch('ingestion.providers.sec_13f_adapter.download_13f_in_date_range')
    def test_fetch_13f_quarter_converts_to_dicts(self, mock_download):
        """Test that DataFrame is converted to list of dicts."""
        mock_df = pd.DataFrame([
            {
                'Company Name': 'TEST COMPANY',
                'CIK': '0000000001',
                'nameOfIssuer': 'APPLE INC',
                'cusip': '037833100',
                'value': 1000000,
                'shares': 1000,
                'filing_date': '2023-11-14'
            }
        ])
        
        mock_download.return_value = mock_df
        
        result = fetch_13f_quarter(
            entity_name='TEST COMPANY',
            quarter_end=date(2023, 9, 30)
        )
        
        # Should return list of dictionaries
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert result[0]['Company Name'] == 'TEST COMPANY'
        assert result[0]['cusip'] == '037833100'
