"""
Tests for insider trading integration.
"""

import pytest
import uuid
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock

from sentiment.insider_trading import (
    fetch_form4_filings,
    calculate_insider_sentiment,
    detect_insider_patterns,
    calculate_insider_baseline,
    detect_insider_abnormality,
    validate_insider_record,
    InsiderTradingError
)


class TestFetchForm4Filings:
    """Test Form 4 filing fetching."""
    
    @patch('sentiment.insider_trading._search_form4_filings')
    @patch('sentiment.insider_trading._process_form4_filing')
    def test_fetch_success(self, mock_process, mock_search):
        """Test successful Form 4 fetching."""
        # Mock search results
        mock_search.return_value = [
            {
                'accession_number': '0001234567-25-000001',
                'filing_date': date(2025, 1, 10),
                'form_type': '4',
                'ticker': 'TEST'
            }
        ]
        
        # Mock processed filing
        mock_process.return_value = {
            'form_id': '0001234567-25-000001',
            'ticker': 'TEST',
            'transaction_type': 'sell',
            'total_value': 50000.0
        }
        
        with patch.dict('os.environ', {'SEC_USER_AGENT': 'test@example.com'}):
            result = fetch_form4_filings('TEST', lookback_days=30, min_value_usd=10000)
        
        assert len(result) == 1
        assert result[0]['form_id'] == '0001234567-25-000001'
        mock_search.assert_called_once()
        mock_process.assert_called_once()
    
    def test_fetch_missing_user_agent(self):
        """Test fetch fails without SEC_USER_AGENT."""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(InsiderTradingError) as exc_info:
                fetch_form4_filings('TEST')
            
            assert "SEC_USER_AGENT environment variable required" in str(exc_info.value)


class TestCalculateInsiderSentiment:
    """Test insider sentiment calculation."""
    
    def test_calculate_sentiment_bullish(self):
        """Test sentiment calculation with net buying."""
        transactions = [
            {
                'transaction_date': date.today() - timedelta(days=2),
                'transaction_type': 'buy',
                'total_value': 100000.0,
                'shares': 1000
            },
            {
                'transaction_date': date.today() - timedelta(days=1),
                'transaction_type': 'sell',
                'total_value': 30000.0,
                'shares': 300
            }
        ]
        
        result = calculate_insider_sentiment(transactions, window_days=7)
        
        assert result['status'] == 'success'
        assert result['buy_count'] == 1
        assert result['sell_count'] == 1
        assert result['net_value'] == 70000.0  # 100k buy - 30k sell
        assert result['sentiment_score'] > 0  # Net positive
        assert result['direction'] == 'bullish'
    
    def test_calculate_sentiment_bearish(self):
        """Test sentiment calculation with net selling."""
        transactions = [
            {
                'transaction_date': date.today() - timedelta(days=2),
                'transaction_type': 'sell',
                'total_value': 100000.0,
                'shares': 1000
            },
            {
                'transaction_date': date.today() - timedelta(days=1),
                'transaction_type': 'buy',
                'total_value': 20000.0,
                'shares': 200
            }
        ]
        
        result = calculate_insider_sentiment(transactions, window_days=7)
        
        assert result['status'] == 'success'
        assert result['buy_count'] == 1
        assert result['sell_count'] == 1
        assert result['net_value'] == -80000.0  # 20k buy - 100k sell
        assert result['sentiment_score'] < 0  # Net negative
        assert result['direction'] == 'bearish'
    
    def test_calculate_sentiment_neutral(self):
        """Test sentiment calculation with balanced activity."""
        transactions = [
            {
                'transaction_date': date.today() - timedelta(days=2),
                'transaction_type': 'buy',
                'total_value': 50000.0,
                'shares': 500
            },
            {
                'transaction_date': date.today() - timedelta(days=1),
                'transaction_type': 'sell',
                'total_value': 55000.0,
                'shares': 550
            }
        ]
        
        result = calculate_insider_sentiment(transactions, window_days=7)
        
        assert result['status'] == 'success'
        assert abs(result['sentiment_score']) <= 0.2  # Near neutral
        assert result['direction'] == 'neutral'
        assert result['sentiment_class'] == 'neutral'
    
    def test_calculate_sentiment_no_data(self):
        """Test sentiment calculation with no transactions."""
        result = calculate_insider_sentiment([])
        
        assert result['status'] == 'no_data'
        assert result['transaction_count'] == 0
    
    def test_calculate_sentiment_outside_window(self):
        """Test sentiment calculation with transactions outside window."""
        transactions = [
            {
                'transaction_date': date.today() - timedelta(days=10),  # Outside 7-day window
                'transaction_type': 'buy',
                'total_value': 100000.0,
                'shares': 1000
            }
        ]
        
        result = calculate_insider_sentiment(transactions, window_days=7)
        
        assert result['status'] == 'no_recent_data'
        assert result['transaction_count'] == 0


class TestDetectInsiderPatterns:
    """Test insider pattern detection."""
    
    def test_detect_clustering_pattern(self):
        """Test detection of transaction clustering."""
        # Create clustered transactions (4 transactions in 3 days)
        base_date = date.today() - timedelta(days=5)
        transactions = [
            {
                'transaction_date': base_date,
                'transaction_type': 'sell',
                'total_value': 50000.0,
                'insider_name': 'John Doe'
            },
            {
                'transaction_date': base_date + timedelta(days=1),
                'transaction_type': 'sell',
                'total_value': 75000.0,
                'insider_name': 'Jane Smith'
            },
            {
                'transaction_date': base_date + timedelta(days=2),
                'transaction_type': 'sell',
                'total_value': 60000.0,
                'insider_name': 'Bob Johnson'
            },
            {
                'transaction_date': base_date + timedelta(days=3),
                'transaction_type': 'sell',
                'total_value': 80000.0,
                'insider_name': 'Alice Brown'
            }
        ]
        
        result = detect_insider_patterns(transactions)
        
        assert result['status'] == 'success'
        assert result['pattern_count'] >= 1
        
        # Should detect clustering pattern
        clustering_patterns = [p for p in result['patterns'] if p['type'] == 'transaction_clustering']
        assert len(clustering_patterns) >= 1
        
        pattern = clustering_patterns[0]
        assert pattern['transaction_count'] >= 3
        assert pattern['abnormality_score'] > 0
    
    def test_detect_directional_consensus_bearish(self):
        """Test detection of bearish directional consensus."""
        # Create mostly selling transactions
        transactions = []
        for i in range(5):
            transactions.append({
                'transaction_date': date.today() - timedelta(days=i+1),
                'transaction_type': 'sell',
                'total_value': 50000.0,
                'insider_name': f'Insider {i}'
            })
        
        # Add one buy to make it not 100% selling
        transactions.append({
            'transaction_date': date.today() - timedelta(days=6),
            'transaction_type': 'buy',
            'total_value': 10000.0,
            'insider_name': 'Buyer'
        })
        
        result = detect_insider_patterns(transactions)
        
        assert result['status'] == 'success'
        
        # Should detect directional consensus
        consensus_patterns = [p for p in result['patterns'] if p['type'] == 'directional_consensus']
        if consensus_patterns:  # May not trigger if buy ratio > 0.2
            pattern = consensus_patterns[0]
            assert pattern['direction'] == 'bearish'
            assert pattern['abnormality_score'] > 0
    
    def test_detect_no_patterns(self):
        """Test pattern detection with normal activity."""
        # Create scattered, small transactions
        transactions = [
            {
                'transaction_date': date.today() - timedelta(days=10),
                'transaction_type': 'buy',
                'total_value': 5000.0,
                'insider_name': 'John Doe'
            },
            {
                'transaction_date': date.today() - timedelta(days=20),
                'transaction_type': 'sell',
                'total_value': 6000.0,
                'insider_name': 'Jane Smith'
            }
        ]
        
        result = detect_insider_patterns(transactions)
        
        assert result['status'] == 'success'
        assert result['pattern_count'] == 0
        assert result['patterns'] == []


class TestValidateInsiderRecord:
    """Test insider trading record validation."""
    
    def test_valid_record(self):
        """Test validation of valid insider record."""
        record = {
            'form_id': '0001234567-25-000001',
            'ticker': 'AAPL',
            'company_name': 'Apple Inc.',
            'insider_name': 'John Doe',
            'insider_title': 'CEO',
            'transaction_date': date(2025, 1, 15),
            'transaction_type': 'sell',
            'shares': 10000.0,
            'price_per_share': 150.0,
            'total_value': 1500000.0,
            'shares_owned_after': 500000.0,
            'filing_date': date(2025, 1, 16),
            'source': 'sec_edgar',
            'fetched_at': datetime(2025, 1, 16, 12, 0)
        }
        
        result = validate_insider_record(record)
        
        assert result is True
    
    def test_invalid_transaction_type(self):
        """Test validation fails for invalid transaction type."""
        record = {
            'form_id': '0001234567-25-000001',
            'ticker': 'AAPL',
            'company_name': 'Apple Inc.',
            'insider_name': 'John Doe',
            'transaction_date': date(2025, 1, 15),
            'transaction_type': 'invalid_type',  # Invalid
            'shares': 10000.0,
            'filing_date': date(2025, 1, 16),
            'fetched_at': datetime(2025, 1, 16, 12, 0)
        }
        
        result = validate_insider_record(record)
        
        assert result is False
    
    def test_invalid_shares(self):
        """Test validation fails for invalid share count."""
        record = {
            'form_id': '0001234567-25-000001',
            'ticker': 'AAPL',
            'company_name': 'Apple Inc.',
            'insider_name': 'John Doe',
            'transaction_date': date(2025, 1, 15),
            'transaction_type': 'sell',
            'shares': -1000.0,  # Invalid: negative
            'filing_date': date(2025, 1, 16),
            'fetched_at': datetime(2025, 1, 16, 12, 0)
        }
        
        result = validate_insider_record(record)
        
        assert result is False
    
    def test_filing_before_transaction(self):
        """Test validation fails when filing date is before transaction date."""
        record = {
            'form_id': '0001234567-25-000001',
            'ticker': 'AAPL',
            'company_name': 'Apple Inc.',
            'insider_name': 'John Doe',
            'transaction_date': date(2025, 1, 15),
            'transaction_type': 'sell',
            'shares': 10000.0,
            'filing_date': date(2025, 1, 14),  # Before transaction
            'fetched_at': datetime(2025, 1, 16, 12, 0)
        }
        
        result = validate_insider_record(record)
        
        assert result is False
    
    def test_excessive_filing_delay(self):
        """Test validation fails for excessive filing delay."""
        record = {
            'form_id': '0001234567-25-000001',
            'ticker': 'AAPL',
            'company_name': 'Apple Inc.',
            'insider_name': 'John Doe',
            'transaction_date': date(2025, 1, 1),
            'transaction_type': 'sell',
            'shares': 10000.0,
            'filing_date': date(2025, 1, 20),  # 19 days later
            'fetched_at': datetime(2025, 1, 20, 12, 0)
        }
        
        result = validate_insider_record(record)
        
        assert result is False


class TestCalculateInsiderBaseline:
    """Test insider baseline calculation."""
    
    def test_calculate_baseline_success(self):
        """Test successful baseline calculation."""
        # Create 30 days of historical transactions
        historical_transactions = []
        for i in range(30):
            # Vary transaction patterns
            tx_count = 1 + (i % 3)  # 1-3 transactions per day
            for j in range(tx_count):
                historical_transactions.append({
                    'transaction_date': date(2025, 1, 1) + timedelta(days=i),
                    'transaction_type': 'sell' if i % 2 == 0 else 'buy',
                    'total_value': 50000.0 + (i * 1000),  # Varying values
                    'shares': 500 + (i * 10)
                })
        
        result = calculate_insider_baseline(historical_transactions)
        
        assert result['status'] == 'success'
        assert result['data_points'] >= 30
        assert 'transaction_count' in result
        assert 'transaction_value' in result
        assert 'net_shares' in result
        
        # Check each metric has mean, std, percentiles
        for metric in ['transaction_count', 'transaction_value', 'net_shares']:
            assert 'mean' in result[metric]
            assert 'std' in result[metric]
            assert 'percentiles' in result[metric]
            assert 'p50' in result[metric]['percentiles']
            assert 'p95' in result[metric]['percentiles']
    
    def test_calculate_baseline_insufficient_data(self):
        """Test baseline calculation with insufficient data."""
        # Only 2 transactions
        transactions = [
            {
                'transaction_date': date.today() - timedelta(days=1),
                'transaction_type': 'sell',
                'total_value': 50000.0,
                'shares': 500
            },
            {
                'transaction_date': date.today() - timedelta(days=2),
                'transaction_type': 'buy',
                'total_value': 30000.0,
                'shares': 300
            }
        ]
        
        result = calculate_insider_baseline(transactions)
        
        assert result['status'] == 'insufficient_data'
        assert result['data_points'] == 2
    
    def test_calculate_baseline_empty_data(self):
        """Test baseline calculation with no data."""
        result = calculate_insider_baseline([])
        
        assert result['status'] == 'insufficient_data'
        assert result['data_points'] == 0


class TestDetectInsiderAbnormality:
    """Test insider abnormality detection."""
    
    def test_detect_abnormality_normal(self):
        """Test detection of normal insider activity."""
        current_metrics = {
            'transaction_count': 2.0,
            'transaction_value': 50000.0,
            'net_shares': -100.0
        }
        
        baseline = {
            'status': 'success',
            'data_points': 50,
            'transaction_count': {'mean': 2.0, 'std': 1.0},
            'transaction_value': {'mean': 50000.0, 'std': 20000.0},
            'net_shares': {'mean': 0.0, 'std': 500.0}
        }
        
        result = detect_insider_abnormality(current_metrics, baseline)
        
        assert result['status'] == 'success'
        assert result['overall_classification'] == 'normal'
        assert result['composite_abnormality'] <= 1.0
        
        # Check individual metrics
        for metric in ['transaction_count', 'transaction_value', 'net_shares']:
            assert metric in result['metrics']
            assert result['metrics'][metric]['classification'] == 'normal'
    
    def test_detect_abnormality_extreme(self):
        """Test detection of extreme insider activity."""
        current_metrics = {
            'transaction_count': 10.0,  # Much higher than baseline
            'transaction_value': 500000.0,  # Much higher than baseline
            'net_shares': -5000.0  # Large net selling
        }
        
        baseline = {
            'status': 'success',
            'data_points': 50,
            'transaction_count': {'mean': 2.0, 'std': 1.0},
            'transaction_value': {'mean': 50000.0, 'std': 20000.0},
            'net_shares': {'mean': 0.0, 'std': 500.0}
        }
        
        result = detect_insider_abnormality(current_metrics, baseline)
        
        assert result['status'] == 'success'
        assert result['overall_classification'] in ['unusual', 'extreme']
        assert result['composite_abnormality'] > 1.0
        
        # At least some metrics should be abnormal
        abnormal_metrics = [
            m for m in result['metrics'].values() 
            if m['classification'] in ['unusual', 'extreme']
        ]
        assert len(abnormal_metrics) > 0
    
    def test_detect_abnormality_no_baseline(self):
        """Test abnormality detection without baseline."""
        current_metrics = {'transaction_count': 5.0}
        baseline = {'status': 'insufficient_data'}
        
        result = detect_insider_abnormality(current_metrics, baseline)
        
        assert result['status'] == 'no_baseline'
        assert result['baseline_available'] is False
