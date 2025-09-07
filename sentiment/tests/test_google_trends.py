"""
Tests for Google Trends integration.
"""

import pytest
import uuid
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

from sentiment.google_trends import (
    create_trends_client,
    fetch_search_interest,
    normalize_trends_data,
    calculate_search_baseline,
    detect_search_abnormality,
    fetch_trends_for_ticker,
    validate_trends_record,
    get_company_name_for_ticker,
    calculate_search_volume_trend,
    GoogleTrendsError
)


class TestCreateTrendsClient:
    """Test Google Trends client creation."""
    
    @patch('sentiment.google_trends.TrendReq')
    def test_create_client_success(self, mock_trend_req):
        """Test successful client creation."""
        mock_client = MagicMock()
        mock_trend_req.return_value = mock_client
        
        result = create_trends_client()
        
        assert result == mock_client
        mock_trend_req.assert_called_once_with(
            hl='en-US',
            tz=360,
            timeout=(10, 25),
            retries=2,
            backoff_factor=0.1
        )
    
    @patch('sentiment.google_trends.TrendReq')
    def test_create_client_failure(self, mock_trend_req):
        """Test client creation failure."""
        mock_trend_req.side_effect = Exception("Connection failed")
        
        with pytest.raises(GoogleTrendsError) as exc_info:
            create_trends_client()
        
        assert "Failed to create Google Trends client" in str(exc_info.value)


class TestFetchSearchInterest:
    """Test search interest fetching."""
    
    @patch('sentiment.google_trends.create_trends_client')
    def test_fetch_success(self, mock_create_client):
        """Test successful search interest fetch."""
        # Mock client and data
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        
        # Create mock interest over time data
        dates = pd.date_range('2025-01-10', '2025-01-16', freq='D')
        mock_data = pd.DataFrame({
            'AAPL': [45, 50, 55, 60, 65, 70, 75]
        }, index=dates)
        
        mock_client.interest_over_time.return_value = mock_data
        mock_client.related_queries.return_value = {
            'AAPL': {
                'top': pd.DataFrame({'query': ['apple stock', 'aapl earnings'], 'value': [100, 80]}),
                'rising': pd.DataFrame({'query': ['apple news'], 'value': [200]})
            }
        }
        
        result = fetch_search_interest('AAPL', timeframe='today 7-d')
        
        assert result['status'] == 'success'
        assert result['ticker'] == 'AAPL'
        assert result['timeframe'] == 'today 7-d'
        assert len(result['data_points']) == 7
        assert result['data_points'][0]['search_volume'] == 45
        assert result['data_points'][-1]['search_volume'] == 75
        
        # Check that related queries are included in last data point
        last_point = result['data_points'][-1]
        assert last_point['related_queries'] is not None
        assert last_point['rising_queries'] is not None
    
    @patch('sentiment.google_trends.create_trends_client')
    def test_fetch_no_data(self, mock_create_client):
        """Test fetch with no data returned."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        
        # Empty dataframe
        mock_client.interest_over_time.return_value = pd.DataFrame()
        
        result = fetch_search_interest('INVALID')
        
        assert result['status'] == 'no_data'
        assert result['ticker'] == 'INVALID'
    
    @patch('sentiment.google_trends.create_trends_client')
    def test_fetch_with_company_name(self, mock_create_client):
        """Test fetch with company name included."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        
        dates = pd.date_range('2025-01-10', '2025-01-12', freq='D')
        mock_data = pd.DataFrame({
            'AAPL': [50, 55, 60],
            'Apple': [45, 50, 55]
        }, index=dates)
        
        mock_client.interest_over_time.return_value = mock_data
        mock_client.related_queries.return_value = {}
        
        result = fetch_search_interest('AAPL', company_name='Apple')
        
        assert result['status'] == 'success'
        assert 'Apple' in result['search_terms']
        mock_client.build_payload.assert_called_once()
        # Check that both AAPL and Apple were included in search terms
        call_args = mock_client.build_payload.call_args[1]
        assert 'AAPL' in call_args['kw_list']
        assert 'Apple' in call_args['kw_list']


class TestCalculateSearchBaseline:
    """Test search baseline calculation."""
    
    def test_calculate_baseline_success(self):
        """Test successful baseline calculation."""
        # Create historical data (30 days)
        historical_data = []
        for i in range(30):
            historical_data.append({
                'search_volume': 40 + (i % 10),  # Varying volumes 40-49
                'date': date(2025, 1, 1) + timedelta(days=i)
            })
        
        result = calculate_search_baseline(historical_data)
        
        assert result['status'] == 'success'
        assert result['data_points'] == 30
        assert 40 <= result['mean_value'] <= 50
        assert result['std_value'] > 0
        assert 'percentiles' in result
        assert 'p50' in result['percentiles']  # Median
        assert 'p95' in result['percentiles']  # 95th percentile
    
    def test_calculate_baseline_insufficient_data(self):
        """Test baseline calculation with insufficient data."""
        # Only 3 days of data
        historical_data = [
            {'search_volume': 45, 'date': date(2025, 1, 1)},
            {'search_volume': 50, 'date': date(2025, 1, 2)},
            {'search_volume': 55, 'date': date(2025, 1, 3)}
        ]
        
        result = calculate_search_baseline(historical_data)
        
        assert result['status'] == 'insufficient_data'
        assert result['data_points'] == 3
    
    def test_calculate_baseline_empty_data(self):
        """Test baseline calculation with empty data."""
        result = calculate_search_baseline([])
        
        assert result['status'] == 'insufficient_data'
        assert result['data_points'] == 0


class TestDetectSearchAbnormality:
    """Test search abnormality detection."""
    
    def test_detect_abnormality_normal(self):
        """Test detection of normal search volume."""
        baseline = {
            'status': 'success',
            'mean_value': 50.0,
            'std_value': 10.0,
            'data_points': 30
        }
        
        # Current volume within 1 standard deviation
        result = detect_search_abnormality(55, baseline)
        
        assert result['status'] == 'success'
        assert result['classification'] == 'normal'
        assert result['direction'] == 'above_normal'
        assert -1.0 <= result['z_score'] <= 1.0
        assert 0.0 <= result['percentile'] <= 1.0
    
    def test_detect_abnormality_unusual(self):
        """Test detection of unusual search volume."""
        baseline = {
            'status': 'success',
            'mean_value': 50.0,
            'std_value': 10.0,
            'data_points': 30
        }
        
        # Current volume 1.5 standard deviations above
        result = detect_search_abnormality(65, baseline)
        
        assert result['status'] == 'success'
        assert result['classification'] == 'unusual'
        assert result['direction'] == 'above_normal'
        assert 1.0 < result['z_score'] <= 2.0
        assert result['percentile'] > 0.8
    
    def test_detect_abnormality_extreme(self):
        """Test detection of extreme search volume."""
        baseline = {
            'status': 'success',
            'mean_value': 50.0,
            'std_value': 10.0,
            'data_points': 30
        }
        
        # Current volume 2.5 standard deviations above
        result = detect_search_abnormality(75, baseline)
        
        assert result['status'] == 'success'
        assert result['classification'] == 'extreme'
        assert result['direction'] == 'above_normal'
        assert result['z_score'] > 2.0
        assert result['percentile'] > 0.95
    
    def test_detect_abnormality_z_score_capping(self):
        """Test Z-score capping at extreme values."""
        baseline = {
            'status': 'success',
            'mean_value': 50.0,
            'std_value': 10.0,
            'data_points': 30
        }
        
        # Current volume 5 standard deviations above (should be capped at 3.0)
        result = detect_search_abnormality(100, baseline, z_score_cap=3.0)
        
        assert result['status'] == 'success'
        assert result['z_score'] == 3.0  # Capped
        assert result['classification'] == 'extreme'
    
    def test_detect_abnormality_no_baseline(self):
        """Test abnormality detection without baseline."""
        baseline = {'status': 'insufficient_data'}
        
        result = detect_search_abnormality(75, baseline)
        
        assert result['status'] == 'no_baseline'
        assert result['baseline_available'] is False
        assert result['current_volume'] == 75
    
    def test_detect_abnormality_zero_std(self):
        """Test abnormality detection with zero standard deviation."""
        baseline = {
            'status': 'success',
            'mean_value': 50.0,
            'std_value': 0.0,  # No variation
            'data_points': 30
        }
        
        result = detect_search_abnormality(50, baseline)
        
        assert result['status'] == 'success'
        assert result['z_score'] == 0.0
        assert result['classification'] == 'normal'


class TestValidateTrendsRecord:
    """Test trends record validation."""
    
    def test_valid_record(self):
        """Test validation of valid trends record."""
        record = {
            'id': str(uuid.uuid4()),
            'ticker': 'AAPL',
            'search_term': 'AAPL',
            'date': date(2025, 1, 15),
            'search_volume': 75,
            'geo': 'US',
            'timeframe': 'today 7-d',
            'related_queries': None,
            'rising_queries': None,
            'fetched_at': datetime(2025, 1, 15, 12, 0)
        }
        
        result = validate_trends_record(record)
        
        assert result is True
    
    def test_invalid_search_volume_range(self):
        """Test validation fails for invalid search volume."""
        record = {
            'id': str(uuid.uuid4()),
            'ticker': 'AAPL',
            'search_term': 'AAPL',
            'date': date(2025, 1, 15),
            'search_volume': 150,  # Invalid: > 100
            'geo': 'US',
            'timeframe': 'today 7-d',
            'fetched_at': datetime(2025, 1, 15, 12, 0)
        }
        
        result = validate_trends_record(record)
        
        assert result is False
    
    def test_invalid_ticker_format(self):
        """Test validation fails for invalid ticker."""
        record = {
            'id': str(uuid.uuid4()),
            'ticker': 'INVALID123',  # Invalid: contains numbers
            'search_term': 'INVALID123',
            'date': date(2025, 1, 15),
            'search_volume': 75,
            'geo': 'US',
            'timeframe': 'today 7-d',
            'fetched_at': datetime(2025, 1, 15, 12, 0)
        }
        
        result = validate_trends_record(record)
        
        assert result is False
    
    def test_missing_required_field(self):
        """Test validation fails for missing required field."""
        record = {
            'id': str(uuid.uuid4()),
            'ticker': 'AAPL',
            # Missing search_term
            'date': date(2025, 1, 15),
            'search_volume': 75,
            'geo': 'US',
            'timeframe': 'today 7-d',
            'fetched_at': datetime(2025, 1, 15, 12, 0)
        }
        
        result = validate_trends_record(record)
        
        assert result is False


class TestGetCompanyNameForTicker:
    """Test company name lookup."""
    
    def test_known_ticker(self):
        """Test lookup for known ticker."""
        result = get_company_name_for_ticker('AAPL')
        assert result == 'Apple'
        
        result = get_company_name_for_ticker('MSFT')
        assert result == 'Microsoft'
    
    def test_unknown_ticker(self):
        """Test lookup for unknown ticker."""
        result = get_company_name_for_ticker('UNKNOWN')
        assert result is None
    
    def test_case_insensitive(self):
        """Test case insensitive lookup."""
        result = get_company_name_for_ticker('aapl')
        assert result == 'Apple'


class TestCalculateSearchVolumeTrend:
    """Test search volume trend calculation."""
    
    def test_calculate_trend_increasing(self):
        """Test trend calculation for increasing search volume."""
        current_data = [
            {'search_volume': 70}, {'search_volume': 75}, {'search_volume': 80}
        ]
        baseline_data = [
            {'search_volume': 45}, {'search_volume': 50}, {'search_volume': 55}
        ]
        
        result = calculate_search_volume_trend(current_data, baseline_data)
        
        assert result['status'] == 'success'
        assert result['current_avg_volume'] == 75.0
        assert result['baseline_avg_volume'] == 50.0
        assert result['trend_percent'] == 50.0  # 50% increase
        assert result['trend_magnitude'] == 'moderate'
        assert result['trend_direction'] == 'increasing'
    
    def test_calculate_trend_decreasing(self):
        """Test trend calculation for decreasing search volume."""
        current_data = [
            {'search_volume': 25}, {'search_volume': 30}, {'search_volume': 35}
        ]
        baseline_data = [
            {'search_volume': 45}, {'search_volume': 50}, {'search_volume': 55}
        ]
        
        result = calculate_search_volume_trend(current_data, baseline_data)
        
        assert result['status'] == 'success'
        assert result['current_avg_volume'] == 30.0
        assert result['baseline_avg_volume'] == 50.0
        assert result['trend_percent'] == -40.0  # 40% decrease
        assert result['trend_magnitude'] == 'moderate'
        assert result['trend_direction'] == 'decreasing'
    
    def test_calculate_trend_stable(self):
        """Test trend calculation for stable search volume."""
        current_data = [
            {'search_volume': 48}, {'search_volume': 50}, {'search_volume': 52}
        ]
        baseline_data = [
            {'search_volume': 48}, {'search_volume': 50}, {'search_volume': 52}
        ]
        
        result = calculate_search_volume_trend(current_data, baseline_data)
        
        assert result['status'] == 'success'
        assert result['trend_percent'] == 0.0
        assert result['trend_magnitude'] == 'minimal'
        assert result['trend_direction'] == 'stable'
    
    def test_calculate_trend_insufficient_data(self):
        """Test trend calculation with insufficient data."""
        current_data = []
        baseline_data = [{'search_volume': 50}]
        
        result = calculate_search_volume_trend(current_data, baseline_data)
        
        assert result['status'] == 'insufficient_data'
        assert result['current_data_points'] == 0
        assert result['baseline_data_points'] == 1


class TestNormalizeTrendsData:
    """Test trends data normalization."""
    
    def test_normalize_success_data(self):
        """Test normalization of successful trends data."""
        trends_result = {
            'status': 'success',
            'ticker': 'AAPL',
            'geo': 'US',
            'timeframe': 'today 7-d',
            'data_points': [
                {
                    'date': date(2025, 1, 15),
                    'search_volume': 75,
                    'search_term': 'AAPL',
                    'related_queries': [{'query': 'apple stock', 'value': 100}],
                    'rising_queries': None
                }
            ],
            'fetched_at': datetime(2025, 1, 15, 12, 0)
        }
        
        result = normalize_trends_data(trends_result, 'AAPL')
        
        assert len(result) == 1
        record = result[0]
        assert record['ticker'] == 'AAPL'
        assert record['search_volume'] == 75
        assert record['geo'] == 'US'
        assert record['timeframe'] == 'today 7-d'
        assert 'id' in record
        # Validate UUID format
        uuid.UUID(record['id'])
    
    def test_normalize_no_data(self):
        """Test normalization of no-data result."""
        trends_result = {
            'status': 'no_data',
            'ticker': 'INVALID'
        }
        
        result = normalize_trends_data(trends_result, 'INVALID')
        
        assert result == []
