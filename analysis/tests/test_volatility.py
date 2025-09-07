"""
Tests for volatility calculation utilities.
Pure functions with synthetic data where standard deviation is known.
"""

import pytest
import numpy as np
import math
from datetime import date

# Import volatility utilities (will be created next)
from analysis.calculations.volatility import (
    log_returns,
    realized_vol,
    rolling_volatility,
    VolatilityError
)


class TestLogReturns:
    """Tests for log returns calculation."""
    
    def test_log_returns_basic(self):
        """Test log returns with known values."""
        # Price series: 100 -> 110 -> 121
        prices = [100.0, 110.0, 121.0]
        
        log_ret = log_returns(prices)
        
        # Should return 2 log returns
        assert len(log_ret) == 2
        
        # Verify calculations
        # ln(110/100) = ln(1.1) ≈ 0.0953
        # ln(121/110) = ln(1.1) ≈ 0.0953
        expected_1 = math.log(110.0 / 100.0)
        expected_2 = math.log(121.0 / 110.0)
        
        assert abs(log_ret[0] - expected_1) < 1e-6
        assert abs(log_ret[1] - expected_2) < 1e-6
    
    def test_log_returns_single_return(self):
        """Test log returns with only 2 prices."""
        prices = [100.0, 105.0]  # +5%
        
        log_ret = log_returns(prices)
        
        assert len(log_ret) == 1
        expected = math.log(105.0 / 100.0)
        assert abs(log_ret[0] - expected) < 1e-6
    
    def test_log_returns_insufficient_data(self):
        """Test with insufficient data."""
        prices = [100.0]  # Only 1 price
        
        with pytest.raises(VolatilityError, match="Insufficient data"):
            log_returns(prices)
    
    def test_log_returns_zero_price(self):
        """Test with zero price."""
        prices = [100.0, 0.0, 110.0]
        
        with pytest.raises(VolatilityError, match="Zero or negative prices"):
            log_returns(prices)
    
    def test_log_returns_negative_price(self):
        """Test with negative price."""
        prices = [100.0, -50.0, 110.0]
        
        with pytest.raises(VolatilityError, match="Zero or negative prices"):
            log_returns(prices)
    
    def test_log_returns_numpy_output(self):
        """Test that output is numpy array."""
        prices = [100.0, 110.0, 121.0]
        log_ret = log_returns(prices)
        
        assert isinstance(log_ret, np.ndarray)
        assert log_ret.dtype == np.float64


class TestRealizedVolatility:
    """Tests for realized volatility calculation."""
    
    def test_realized_vol_known_series(self):
        """Test volatility with known standard deviation."""
        # Create series with known properties
        # Daily returns of exactly 1% each day
        # std = 0, so volatility should be 0
        log_ret = np.array([0.01, 0.01, 0.01, 0.01, 0.01])
        
        vol = realized_vol(log_ret, window=5, annualize=252)
        
        # Standard deviation of constant series is 0
        assert abs(vol) < 1e-10
    
    def test_realized_vol_variable_series(self):
        """Test volatility with variable returns."""
        # Returns: [0, 0.02, -0.02, 0.02, -0.02]
        # Mean = 0, variance = 0.0016, std = 0.04
        log_ret = np.array([0.0, 0.02, -0.02, 0.02, -0.02])
        
        vol = realized_vol(log_ret, window=5, annualize=1)  # No annualization
        
        # Standard deviation should be 0.04
        expected_std = np.std(log_ret, ddof=1)  # Sample std
        assert abs(vol - expected_std) < 1e-6
    
    def test_realized_vol_annualization(self):
        """Test annualization factor."""
        log_ret = np.array([0.01, -0.01, 0.01, -0.01, 0.01])
        
        # Without annualization
        vol_daily = realized_vol(log_ret, window=5, annualize=1)
        
        # With annualization
        vol_annual = realized_vol(log_ret, window=5, annualize=252)
        
        # Should be scaled by sqrt(252)
        expected_annual = vol_daily * math.sqrt(252)
        assert abs(vol_annual - expected_annual) < 1e-6
    
    def test_realized_vol_insufficient_data(self):
        """Test with insufficient data for window."""
        log_ret = np.array([0.01, 0.02])  # Only 2 returns
        
        with pytest.raises(VolatilityError, match="Insufficient data"):
            realized_vol(log_ret, window=5)  # Need 5 returns
    
    def test_realized_vol_minimum_window(self):
        """Test with minimum window size."""
        log_ret = np.array([0.01, 0.02])  # 2 returns
        
        # Window of 2 should work
        vol = realized_vol(log_ret, window=2, annualize=1)
        
        # Should calculate std of 2 values
        expected = np.std([0.01, 0.02], ddof=1)
        assert abs(vol - expected) < 1e-6
    
    def test_realized_vol_empty_array(self):
        """Test with empty log returns."""
        log_ret = np.array([])
        
        with pytest.raises(VolatilityError, match="Insufficient data"):
            realized_vol(log_ret, window=1)


class TestRollingVolatility:
    """Tests for rolling volatility calculation."""
    
    def test_rolling_volatility_basic(self):
        """Test rolling volatility with sufficient data."""
        # 10 log returns for rolling 5-day windows
        log_ret = np.array([0.01, -0.01, 0.02, -0.02, 0.01, 0.00, 0.01, -0.01, 0.02, -0.01])
        
        rolling_vol = rolling_volatility(log_ret, window=5, annualize=252)
        
        # Should return 6 volatility values (10 - 5 + 1)
        assert len(rolling_vol) == 6
        assert isinstance(rolling_vol, np.ndarray)
        
        # All values should be positive
        assert all(vol >= 0 for vol in rolling_vol)
    
    def test_rolling_volatility_single_window(self):
        """Test rolling volatility with window equal to data length."""
        log_ret = np.array([0.01, -0.01, 0.02, -0.02, 0.01])
        
        rolling_vol = rolling_volatility(log_ret, window=5, annualize=1)
        
        # Should return 1 value
        assert len(rolling_vol) == 1
        
        # Should equal realized_vol for same window
        expected = realized_vol(log_ret, window=5, annualize=1)
        assert abs(rolling_vol[0] - expected) < 1e-6
    
    def test_rolling_volatility_insufficient_data(self):
        """Test with insufficient data for rolling windows."""
        log_ret = np.array([0.01, 0.02])  # Only 2 returns
        
        with pytest.raises(VolatilityError, match="Insufficient data"):
            rolling_volatility(log_ret, window=5)  # Need 5+ returns
    
    def test_rolling_volatility_current_value(self):
        """Test that rolling volatility returns most recent value correctly."""
        # Create series where we can verify the last window
        log_ret = np.array([0.01, 0.02, 0.01, 0.02, 0.01, 0.00, 0.01])  # 7 returns
        
        rolling_vol = rolling_volatility(log_ret, window=3, annualize=1)
        
        # Should return 5 values (7 - 3 + 1)
        assert len(rolling_vol) == 5
        
        # Last value should be volatility of last 3 returns: [0.00, 0.01]
        last_3_returns = log_ret[-3:]  # [0.01, 0.00, 0.01]
        expected_last = np.std(last_3_returns, ddof=1)
        assert abs(rolling_vol[-1] - expected_last) < 1e-6


class TestVolatilityIntegration:
    """Integration tests for volatility calculations."""
    
    def test_price_to_volatility_pipeline(self):
        """Test complete pipeline from prices to volatility."""
        # Price series with known volatility characteristics
        # Prices oscillate ±5% around 100
        prices = [100.0, 105.0, 100.0, 95.0, 100.0, 105.0, 100.0]
        
        # Calculate log returns
        log_ret = log_returns(prices)
        assert len(log_ret) == 6
        
        # Calculate rolling volatility
        rolling_vol = rolling_volatility(log_ret, window=3, annualize=252)
        
        # Should have some volatility values
        assert len(rolling_vol) == 4  # 6 - 3 + 1
        assert all(vol > 0 for vol in rolling_vol)  # Should be positive
        
        # Calculate current volatility
        current_vol = realized_vol(log_ret, window=len(log_ret), annualize=252)
        assert current_vol > 0
    
    def test_constant_price_zero_volatility(self):
        """Test that constant prices give zero volatility."""
        # All prices the same
        prices = [100.0, 100.0, 100.0, 100.0, 100.0]
        
        log_ret = log_returns(prices)
        
        # All log returns should be 0
        assert all(abs(ret) < 1e-10 for ret in log_ret)
        
        # Volatility should be 0 (or very close)
        vol = realized_vol(log_ret, window=len(log_ret), annualize=1)
        assert abs(vol) < 1e-10
    
    def test_high_volatility_series(self):
        """Test with high volatility series."""
        # Highly volatile: 100 -> 150 -> 75 -> 125 -> 90
        prices = [100.0, 150.0, 75.0, 125.0, 90.0]
        
        log_ret = log_returns(prices)
        vol = realized_vol(log_ret, window=len(log_ret), annualize=252)
        
        # Should have high volatility (>50% annualized)
        assert vol > 0.50  # >50% volatility
    
    def test_nan_handling_policy(self):
        """Test explicit NaN handling policy."""
        # Series with NaN should raise error (fail-closed policy)
        log_ret = np.array([0.01, np.nan, 0.02])
        
        with pytest.raises(VolatilityError, match="NaN values"):
            realized_vol(log_ret, window=3)
    
    def test_infinite_handling_policy(self):
        """Test infinite value handling."""
        log_ret = np.array([0.01, np.inf, 0.02])
        
        with pytest.raises(VolatilityError, match="Infinite values"):
            realized_vol(log_ret, window=3)
