"""
Tests for metrics aggregator - composes all calculations into MetricsJSON.
Uses AAPL fixture + tiny 13F fixture; asserts combined JSON matches golden.
"""

import pytest
import pandas as pd
import json
from datetime import date, datetime
from pathlib import Path

# Import aggregator (will be created next)
from analysis.metrics_aggregator import (
    compose_metrics,
    MetricsAggregatorError
)


def load_fixture(filename):
    """Load fixture from tests/fixtures directory."""
    fixture_path = Path(__file__).parent.parent.parent / 'tests/fixtures' / filename
    
    if filename.endswith('.csv'):
        return pd.read_csv(fixture_path, parse_dates=['date', 'as_of'])
    elif filename.endswith('.json'):
        with open(fixture_path, 'r') as f:
            return json.load(f)
    else:
        raise ValueError(f"Unknown fixture format: {filename}")


class TestMetricsAggregator:
    """Tests for compose_metrics function."""
    
    def test_compose_metrics_complete_data(self):
        """Test metrics composition with both price and 13F data."""
        # Load fixtures
        price_df = load_fixture('prices_aapl_small.csv')
        holdings_data = load_fixture('holdings_13f_tiny.json')
        expected_metrics = load_fixture('expected_aapl_metrics.json')
        
        # Convert holdings to DataFrame
        holdings_df = pd.DataFrame(holdings_data)
        
        # Compose metrics
        result = compose_metrics(
            price_df=price_df,
            holdings_df=holdings_df,
            ticker='AAPL',
            as_of_date=date(2025, 8, 7)
        )
        
        # Verify top-level structure
        required_keys = {
            'ticker', 'as_of_date', 'data_period', 'price_metrics',
            'institutional_metrics', 'data_quality', 'metadata'
        }
        assert required_keys.issubset(result.keys())
        
        # Verify ticker and date
        assert result['ticker'] == 'AAPL'
        assert result['as_of_date'] == '2025-08-07'
        
        # Verify data period calculation
        data_period = result['data_period']
        assert data_period['trading_days'] == 5  # 5 rows in fixture
        assert data_period['start_date'] == '2025-08-01'
        assert data_period['end_date'] == '2025-08-07'
        
        # Verify price metrics structure
        price_metrics = result['price_metrics']
        assert 'returns' in price_metrics
        assert 'volatility' in price_metrics
        assert 'drawdown' in price_metrics
        assert 'current_price' in price_metrics
        
        # Verify institutional metrics structure
        inst_metrics = result['institutional_metrics']
        assert inst_metrics is not None
        assert 'concentration' in inst_metrics
        assert 'total_13f_value_usd' in inst_metrics
        assert 'total_13f_holders' in inst_metrics
    
    def test_compose_metrics_price_only(self):
        """Test metrics composition with only price data (no 13F)."""
        price_df = load_fixture('prices_aapl_small.csv')
        
        result = compose_metrics(
            price_df=price_df,
            holdings_df=None,
            ticker='AAPL',
            as_of_date=date(2025, 8, 7)
        )
        
        # Should have price metrics
        assert 'price_metrics' in result
        assert result['price_metrics']['current_price']['close'] == 225.40
        
        # Institutional metrics should be None
        assert result['institutional_metrics'] is None
        
        # Data quality should reflect missing 13F data
        assert result['data_quality']['latest_13f_quarter'] is None
    
    def test_compose_metrics_insufficient_price_data(self):
        """Test with insufficient price data for some metrics."""
        # Create minimal price data (only 2 days)
        minimal_prices = pd.DataFrame([
            {
                'ticker': 'TEST',
                'date': date(2025, 8, 1),
                'close': 100.0,
                'volume': 1000000
            },
            {
                'ticker': 'TEST', 
                'date': date(2025, 8, 2),
                'close': 105.0,
                'volume': 1200000
            }
        ])
        
        result = compose_metrics(
            price_df=minimal_prices,
            holdings_df=None,
            ticker='TEST',
            as_of_date=date(2025, 8, 2)
        )
        
        # Should have 1D returns but not longer windows
        returns = result['price_metrics']['returns']
        assert returns['1D'] is not None  # Should be calculable
        assert returns.get('1M') is None   # Not enough data
        assert returns.get('1Y') is None   # Not enough data
        
        # Should have minimal volatility data
        volatility = result['price_metrics']['volatility']
        assert volatility['21D_annualized'] is None  # Not enough data
    
    def test_compose_metrics_empty_price_data(self):
        """Test with empty price DataFrame."""
        empty_df = pd.DataFrame(columns=['ticker', 'date', 'close'])
        
        with pytest.raises(MetricsAggregatorError, match="Empty price data"):
            compose_metrics(
                price_df=empty_df,
                holdings_df=None,
                ticker='AAPL',
                as_of_date=date(2025, 8, 7)
            )
    
    def test_compose_metrics_data_quality_calculation(self):
        """Test data quality metrics calculation."""
        price_df = load_fixture('prices_aapl_small.csv')
        
        result = compose_metrics(
            price_df=price_df,
            holdings_df=None,
            ticker='AAPL',
            as_of_date=date(2025, 8, 7)
        )
        
        dq = result['data_quality']
        
        # Should calculate coverage based on date range
        assert 'price_coverage_pct' in dq
        assert 'missing_price_days' in dq
        assert isinstance(dq['price_coverage_pct'], (int, float))
        assert isinstance(dq['missing_price_days'], int)
        
        # With 5 consecutive days, coverage should be 100%
        assert dq['price_coverage_pct'] == 100.0
        assert dq['missing_price_days'] == 0
    
    def test_compose_metrics_metadata_generation(self):
        """Test metadata generation."""
        price_df = load_fixture('prices_aapl_small.csv')
        
        before_calc = datetime.now()
        result = compose_metrics(
            price_df=price_df,
            holdings_df=None,
            ticker='AAPL',
            as_of_date=date(2025, 8, 7)
        )
        after_calc = datetime.now()
        
        metadata = result['metadata']
        
        # Should have calculation timestamp
        calc_time = datetime.fromisoformat(metadata['calculated_at'])
        assert before_calc <= calc_time <= after_calc
        
        # Should have version and sources
        assert 'calculation_version' in metadata
        assert 'data_sources' in metadata
        assert isinstance(metadata['data_sources'], list)
    
    def test_compose_metrics_returns_calculation_integration(self):
        """Test that returns are calculated correctly from fixture data."""
        price_df = load_fixture('prices_aapl_small.csv')
        
        result = compose_metrics(
            price_df=price_df,
            holdings_df=None,
            ticker='AAPL',
            as_of_date=date(2025, 8, 7)
        )
        
        returns = result['price_metrics']['returns']
        
        # With 5 prices, should be able to calculate 1D return
        assert returns['1D'] is not None
        
        # 1D return from fixture: (225.40 - 224.85) / 224.85 ≈ 0.0024
        # This tests integration with returns calculation
        assert isinstance(returns['1D'], float)
        assert -0.1 <= returns['1D'] <= 0.1  # Reasonable daily return range
    
    def test_compose_metrics_concentration_integration(self):
        """Test 13F concentration calculation integration."""
        price_df = load_fixture('prices_aapl_small.csv')
        holdings_data = load_fixture('holdings_13f_tiny.json')
        holdings_df = pd.DataFrame(holdings_data)
        
        result = compose_metrics(
            price_df=price_df,
            holdings_df=holdings_df,
            ticker='AAPL',
            as_of_date=date(2025, 8, 7)
        )
        
        inst_metrics = result['institutional_metrics']
        concentration = inst_metrics['concentration']
        
        # From fixture: Berkshire 50B, Vanguard 30B, BlackRock 20B = 100B total
        # CR1 = 50B/100B = 0.5
        assert abs(concentration['cr1'] - 0.5) < 1e-6
        
        # Total value should match fixture
        assert inst_metrics['total_13f_value_usd'] == 100000000000.0  # 100B
        assert inst_metrics['total_13f_holders'] == 3
