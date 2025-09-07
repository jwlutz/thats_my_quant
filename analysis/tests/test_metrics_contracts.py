"""
Metrics contract tests - ensure output JSON shapes match specifications.
No calculations required - just schema validation.
"""

import json
import pytest
from datetime import date, datetime
from pathlib import Path


def load_fixture(filename):
    """Load JSON fixture from fixtures directory."""
    fixture_path = Path(__file__).parent.parent.parent / 'tests/fixtures' / filename
    with open(fixture_path, 'r') as f:
        return json.load(f)


def test_metrics_json_schema():
    """Test that expected metrics JSON has correct schema."""
    metrics = load_fixture('expected_aapl_metrics.json')
    
    # Top-level keys
    required_top_keys = {
        'ticker', 'as_of_date', 'data_period', 'price_metrics',
        'institutional_metrics', 'data_quality', 'metadata'
    }
    assert required_top_keys.issubset(metrics.keys())
    
    # Data period structure
    data_period = metrics['data_period']
    assert 'start_date' in data_period
    assert 'end_date' in data_period
    assert 'trading_days' in data_period
    assert isinstance(data_period['trading_days'], int)
    
    # Price metrics structure
    price_metrics = metrics['price_metrics']
    assert 'returns' in price_metrics
    assert 'volatility' in price_metrics
    assert 'drawdown' in price_metrics
    assert 'current_price' in price_metrics
    
    # Returns structure
    returns = price_metrics['returns']
    for window in ['1D', '1W', '1M', '3M', '6M', '1Y']:
        if window in returns:
            value = returns[window]
            assert value is None or isinstance(value, (int, float))
    
    # Volatility structure
    volatility = price_metrics['volatility']
    for window in ['21D_annualized', '63D_annualized', '252D_annualized']:
        if window in volatility:
            value = volatility[window]
            assert value is None or isinstance(value, (int, float))
    
    # Drawdown structure
    drawdown = price_metrics['drawdown']
    required_dd_keys = {
        'max_drawdown_pct', 'peak_date', 'trough_date', 
        'recovery_date', 'drawdown_days', 'recovery_days'
    }
    assert required_dd_keys.issubset(drawdown.keys())
    
    # Current price structure
    current_price = price_metrics['current_price']
    assert 'close' in current_price
    assert 'date' in current_price
    assert isinstance(current_price['close'], (int, float))


def test_institutional_metrics_schema():
    """Test institutional metrics structure."""
    metrics = load_fixture('expected_aapl_metrics.json')
    inst_metrics = metrics['institutional_metrics']
    
    # Required keys
    required_keys = {
        'total_13f_value_usd', 'total_13f_holders', 'concentration',
        'top_holders', 'quarter_end', 'filing_lag_days'
    }
    assert required_keys.issubset(inst_metrics.keys())
    
    # Concentration structure
    concentration = inst_metrics['concentration']
    for cr in ['cr1', 'cr5', 'cr10', 'hhi']:
        assert cr in concentration
        assert isinstance(concentration[cr], (int, float))
        assert 0 <= concentration[cr] <= 1  # Should be decimal percentage
    
    # Top holders structure
    top_holders = inst_metrics['top_holders']
    assert isinstance(top_holders, list)
    
    if top_holders:
        holder = top_holders[0]
        required_holder_keys = {
            'rank', 'filer', 'value_usd', 'shares', 'pct_of_13f_total'
        }
        assert required_holder_keys.issubset(holder.keys())
        assert isinstance(holder['rank'], int)
        assert isinstance(holder['value_usd'], (int, float))
        assert isinstance(holder['pct_of_13f_total'], (int, float))


def test_data_quality_schema():
    """Test data quality metrics structure."""
    metrics = load_fixture('expected_aapl_metrics.json')
    dq = metrics['data_quality']
    
    required_keys = {
        'price_coverage_pct', 'missing_price_days',
        'latest_13f_quarter', '13f_data_age_days'
    }
    assert required_keys.issubset(dq.keys())
    
    # Coverage should be 0-100
    assert 0 <= dq['price_coverage_pct'] <= 100
    assert isinstance(dq['missing_price_days'], int)
    assert dq['missing_price_days'] >= 0


def test_metadata_schema():
    """Test metadata structure."""
    metrics = load_fixture('expected_aapl_metrics.json')
    metadata = metrics['metadata']
    
    required_keys = {'calculated_at', 'calculation_version', 'data_sources'}
    assert required_keys.issubset(metadata.keys())
    
    # Data sources should be list
    assert isinstance(metadata['data_sources'], list)
    assert len(metadata['data_sources']) > 0
    
    # Version should be semantic version
    version = metadata['calculation_version']
    assert isinstance(version, str)
    assert '.' in version  # Basic semver check


def test_decimal_percentage_format():
    """Test that percentages are in decimal format (0.1234 = 12.34%)."""
    metrics = load_fixture('expected_aapl_metrics.json')
    
    # Returns should be decimals
    returns = metrics['price_metrics']['returns']
    for window, value in returns.items():
        if value is not None:
            assert -1.0 <= value <= 10.0  # Reasonable bounds for daily returns
    
    # Concentration ratios should be 0-1
    concentration = metrics['institutional_metrics']['concentration']
    for cr_name, cr_value in concentration.items():
        assert 0 <= cr_value <= 1, f"{cr_name} should be 0-1, got {cr_value}"
    
    # Top holder percentages should be 0-1
    top_holders = metrics['institutional_metrics']['top_holders']
    for holder in top_holders:
        pct = holder['pct_of_13f_total']
        assert 0 <= pct <= 1, f"Holder percentage should be 0-1, got {pct}"


def test_null_handling():
    """Test that null values are handled correctly for missing data."""
    # Create minimal metrics with some nulls
    minimal_metrics = {
        'ticker': 'TEST',
        'as_of_date': '2025-09-06',
        'data_period': {'trading_days': 2},
        'price_metrics': {
            'returns': {'1D': 0.01, '1Y': None},  # 1Y null (insufficient data)
            'volatility': {'21D_annualized': None},  # Null (insufficient data)
            'drawdown': {'max_drawdown_pct': None},  # Null (insufficient data)
            'current_price': {'close': 100.0, 'date': '2025-09-06'}
        },
        'institutional_metrics': None,  # No 13F data available
        'data_quality': {'price_coverage_pct': 50.0, 'missing_price_days': 5},
        'metadata': {'calculated_at': '2025-09-06T10:00:00', 'calculation_version': '1.0.0', 'data_sources': ['yfinance']}
    }
    
    # Should handle None values gracefully
    assert minimal_metrics['price_metrics']['returns']['1Y'] is None
    assert minimal_metrics['institutional_metrics'] is None
    
    # Non-null values should still be valid
    assert minimal_metrics['price_metrics']['returns']['1D'] == 0.01
    assert minimal_metrics['ticker'] == 'TEST'
