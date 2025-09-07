"""
Tests for guardrails and data quality validation.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta

from analysis.guardrails import (
    validate_sufficient_data_for_metrics,
    detect_conflicting_13f_rows,
    validate_numeric_inputs,
    check_data_freshness,
    validate_price_data_integrity,
    run_all_guardrails,
    DataQualityError,
    DataQualityWarning
)


class TestDataSufficiency:
    """Tests for data sufficiency validation."""
    
    def test_sufficient_data_all_windows(self):
        """Test with sufficient data for all windows."""
        # 300 trading days (> 1 year)
        price_df = pd.DataFrame({
            'ticker': ['AAPL'] * 300,
            'date': [date(2024, 1, 1) + timedelta(days=i) for i in range(300)],
            'close': [100.0] * 300
        })
        
        available, insufficient = validate_sufficient_data_for_metrics(
            price_df, ['1D', '1W', '1M', '3M', '6M', '1Y']
        )
        
        assert set(available) == {'1D', '1W', '1M', '3M', '6M', '1Y'}
        assert insufficient == []
    
    def test_insufficient_data_1y_critical(self):
        """Test critical error for insufficient 1Y data."""
        # Only 100 trading days (< 150 threshold)
        price_df = pd.DataFrame({
            'ticker': ['AAPL'] * 100,
            'date': [date(2024, 1, 1) + timedelta(days=i) for i in range(100)],
            'close': [100.0] * 100
        })
        
        with pytest.raises(DataQualityError, match="Insufficient data for 1Y analysis"):
            validate_sufficient_data_for_metrics(price_df, ['1Y'])
    
    def test_sufficient_data_partial_windows(self):
        """Test with data sufficient for some windows."""
        # 30 trading days
        price_df = pd.DataFrame({
            'ticker': ['AAPL'] * 30,
            'date': [date(2024, 1, 1) + timedelta(days=i) for i in range(30)],
            'close': [100.0] * 30
        })
        
        available, insufficient = validate_sufficient_data_for_metrics(
            price_df, ['1D', '1W', '1M', '3M']
        )
        
        assert '1D' in available
        assert '1W' in available  
        assert '1M' in available
        assert '3M' in insufficient


class TestConflictDetection:
    """Tests for 13F conflict detection."""
    
    def test_no_conflicts(self):
        """Test holdings data with no conflicts."""
        holdings_df = pd.DataFrame([
            {'cik': '001', 'cusip': '123456789', 'as_of': date(2024, 9, 30), 'value_usd': 1000000, 'shares': 1000},
            {'cik': '002', 'cusip': '987654321', 'as_of': date(2024, 9, 30), 'value_usd': 2000000, 'shares': 2000}
        ])
        
        conflicts = detect_conflicting_13f_rows(holdings_df)
        assert conflicts == []
    
    def test_minor_conflicts(self):
        """Test with minor conflicts (under threshold)."""
        holdings_df = pd.DataFrame([
            {'cik': '001', 'cusip': '123456789', 'as_of': date(2024, 9, 30), 'value_usd': 1000000, 'shares': 1000},
            {'cik': '001', 'cusip': '123456789', 'as_of': date(2024, 9, 30), 'value_usd': 1050000, 'shares': 1050},  # 5% diff
            {'cik': '002', 'cusip': '987654321', 'as_of': date(2024, 9, 30), 'value_usd': 2000000, 'shares': 2000}
        ])
        
        conflicts = detect_conflicting_13f_rows(holdings_df)
        assert len(conflicts) == 0  # Under 10% threshold
    
    def test_major_conflicts_critical(self):
        """Test with major conflicts that should trigger error."""
        # Create many conflicting rows (>5% of total)
        base_data = []
        for i in range(10):
            # Each holding appears twice with different values
            base_data.extend([
                {'cik': f'00{i}', 'cusip': f'12345678{i}', 'as_of': date(2024, 9, 30), 'value_usd': 1000000, 'shares': 1000},
                {'cik': f'00{i}', 'cusip': f'12345678{i}', 'as_of': date(2024, 9, 30), 'value_usd': 1500000, 'shares': 1500}  # 50% diff
            ])
        
        holdings_df = pd.DataFrame(base_data)
        
        with pytest.raises(DataQualityError, match="High conflict rate"):
            detect_conflicting_13f_rows(holdings_df)


class TestNumericValidation:
    """Tests for numeric input validation."""
    
    def test_valid_metrics(self):
        """Test with valid metrics (should not raise)."""
        metrics = {
            'price_metrics': {
                'returns': {'1D': 0.05, '1M': 0.12},
                'volatility': {'21D_annualized': 0.25},
                'drawdown': {'max_drawdown_pct': -0.15}
            },
            'institutional_metrics': {
                'concentration': {'cr1': 0.45, 'cr5': 0.78, 'hhi': 0.23}
            }
        }
        
        # Should not raise
        validate_numeric_inputs(metrics)
    
    def test_nan_values_error(self):
        """Test that NaN values trigger error."""
        metrics = {
            'price_metrics': {
                'returns': {'1D': float('nan')},  # NaN return
            }
        }
        
        with pytest.raises(DataQualityError, match="NaN value found"):
            validate_numeric_inputs(metrics)
    
    def test_infinite_values_error(self):
        """Test that infinite values trigger error."""
        metrics = {
            'price_metrics': {
                'volatility': {'21D_annualized': float('inf')}  # Infinite volatility
            }
        }
        
        with pytest.raises(DataQualityError, match="Infinite value found"):
            validate_numeric_inputs(metrics)
    
    def test_unrealistic_returns_error(self):
        """Test that unrealistic returns trigger error."""
        metrics = {
            'price_metrics': {
                'returns': {'1D': 15.0}  # 1500% daily return
            }
        }
        
        with pytest.raises(DataQualityError, match="Unrealistic percentage"):
            validate_numeric_inputs(metrics)


class TestDataFreshness:
    """Tests for data freshness checking."""
    
    def test_fresh_data_no_warnings(self):
        """Test with fresh data (no warnings)."""
        # Recent price data
        price_df = pd.DataFrame({
            'date': [date.today() - timedelta(days=1)]  # Yesterday
        })
        
        # Recent 13F data
        holdings_df = pd.DataFrame({
            'as_of': [date.today() - timedelta(days=30)]  # 1 month ago
        })
        
        warnings = check_data_freshness(price_df, holdings_df)
        assert warnings == []
    
    def test_stale_price_data_warning(self):
        """Test with stale price data."""
        # Old price data
        price_df = pd.DataFrame({
            'date': [date.today() - timedelta(days=30)]  # 30 days old
        })
        
        warnings = check_data_freshness(price_df, None, max_price_age_days=7)
        assert len(warnings) == 1
        assert 'Price data is 30 days old' in warnings[0]
    
    def test_stale_13f_data_warning(self):
        """Test with stale 13F data."""
        price_df = pd.DataFrame({'date': [date.today()]})
        
        # Old 13F data
        holdings_df = pd.DataFrame({
            'as_of': [date.today() - timedelta(days=200)]  # 200 days old
        })
        
        warnings = check_data_freshness(price_df, holdings_df, max_13f_age_days=120)
        assert len(warnings) == 1
        assert '13F data is 200 days old' in warnings[0]


class TestPriceIntegrity:
    """Tests for price data integrity validation."""
    
    def test_valid_prices_no_warnings(self):
        """Test with valid price data."""
        price_df = pd.DataFrame({
            'date': [date(2025, 8, 1), date(2025, 8, 2)],
            'open': [100.0, 102.0],
            'high': [105.0, 106.0],
            'low': [99.0, 101.0],
            'close': [103.0, 104.0],
            'volume': [1000000, 1200000]
        })
        
        warnings = validate_price_data_integrity(price_df)
        assert warnings == []
    
    def test_large_price_movement_warning(self):
        """Test detection of large price movements."""
        price_df = pd.DataFrame({
            'date': [date(2025, 8, 1), date(2025, 8, 2)],
            'close': [100.0, 150.0]  # 50% jump
        })
        
        warnings = validate_price_data_integrity(price_df)
        assert len(warnings) == 1
        assert 'Large price movement' in warnings[0]
        assert '50.0%' in warnings[0]
    
    def test_zero_volume_warning(self):
        """Test detection of zero volume days."""
        price_df = pd.DataFrame({
            'date': [date(2025, 8, 1), date(2025, 8, 2)],
            'volume': [1000000, 0]  # Zero volume
        })
        
        warnings = validate_price_data_integrity(price_df)
        assert len(warnings) == 1
        assert 'Zero volume detected' in warnings[0]
    
    def test_price_logic_violation_warning(self):
        """Test detection of price logic violations."""
        price_df = pd.DataFrame({
            'date': [date(2025, 8, 1)],
            'open': [100.0],
            'high': [95.0],  # High < Open (invalid)
            'low': [98.0],
            'close': [99.0]
        })
        
        warnings = validate_price_data_integrity(price_df)
        assert len(warnings) == 1
        assert 'Price logic violations' in warnings[0]
