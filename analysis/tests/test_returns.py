"""
Tests for returns calculation utilities.
Pure functions with deterministic synthetic data for hand verification.
"""

import pytest
import numpy as np
import pandas as pd
from datetime import date, datetime

# Import returns utilities (will be created next)
from analysis.calculations.returns import (
    window_ends,
    simple_returns,
    simple_returns_vectorized,
    ReturnsError
)


class TestWindowEnds:
    """Tests for window_ends function."""
    
    def test_window_ends_basic(self):
        """Test window ends calculation with simple date series."""
        # 10 consecutive trading days
        trading_dates = [
            date(2025, 8, 1), date(2025, 8, 4), date(2025, 8, 5), 
            date(2025, 8, 6), date(2025, 8, 7), date(2025, 8, 8),
            date(2025, 8, 11), date(2025, 8, 12), date(2025, 8, 13), 
            date(2025, 8, 14)  # 10 days total
        ]
        
        windows = [1, 5, 10]
        result = window_ends(trading_dates, windows)
        
        # Should return dict with window keys
        assert set(result.keys()) == {'1D', '5D', '10D'}
        
        # 1D: can calculate for all dates except first
        assert result['1D'] == 9  # 10 dates - 1
        
        # 5D: can calculate for dates 5+ (5 calculations)
        assert result['5D'] == 5  # 10 dates - 5 = 5
        
        # 10D: can calculate for last date only (0 calculations - need 11 prices for 10D return)
        assert result['10D'] == 0  # 10 dates - 10 = 0
    
    def test_window_ends_insufficient_data(self):
        """Test when insufficient data for some windows."""
        # Only 3 trading days
        trading_dates = [
            date(2025, 8, 1), date(2025, 8, 4), date(2025, 8, 5)
        ]
        
        windows = [1, 5, 21]
        result = window_ends(trading_dates, windows)
        
        # Should return dict with all keys
        assert set(result.keys()) == {'1D', '5D', '21D'}
        
        # 1D: possible for 2 dates
        assert result['1D'] == 2
        
        # 5D, 21D: not enough data
        assert result['5D'] == 0
        assert result['21D'] == 0
    
    def test_window_ends_empty_dates(self):
        """Test with empty date list."""
        result = window_ends([], [1, 5, 21])
        
        assert result == {'1D': 0, '5D': 0, '21D': 0}
    
    def test_window_ends_default_windows(self):
        """Test default window set."""
        # 300 days (more than 1Y)
        trading_dates = [date(2024, 1, 1) for _ in range(300)]
        
        result = window_ends(trading_dates)
        
        # Should have all default windows
        expected_keys = {'1D', '5D', '21D', '63D', '126D', '252D'}
        assert set(result.keys()) == expected_keys
        
        # All should be calculable
        assert result['1D'] == 299  # 300 - 1
        assert result['252D'] == 48  # 300 - 252 = 48


class TestSimpleReturns:
    """Tests for simple returns calculation."""
    
    def test_simple_returns_basic(self):
        """Test simple returns with known values."""
        # Price series: 100 -> 110 -> 105
        prices = [100.0, 110.0, 105.0]
        
        # 1-day returns
        ret_1d = simple_returns(prices, k=1)
        expected = (105.0 / 110.0) - 1  # -4.55%
        assert abs(ret_1d - expected) < 1e-6
        
        # 2-day returns  
        ret_2d = simple_returns(prices, k=2)
        expected = (105.0 / 100.0) - 1  # +5%
        assert abs(ret_2d - expected) < 1e-6
    
    def test_simple_returns_positive(self):
        """Test positive returns."""
        prices = [100.0, 120.0]  # +20%
        ret = simple_returns(prices, k=1)
        expected = 0.20
        assert abs(ret - expected) < 1e-6
    
    def test_simple_returns_negative(self):
        """Test negative returns."""
        prices = [100.0, 80.0]  # -20%
        ret = simple_returns(prices, k=1)
        expected = -0.20
        assert abs(ret - expected) < 1e-6
    
    def test_simple_returns_insufficient_data(self):
        """Test with insufficient data."""
        prices = [100.0]  # Only 1 price
        
        with pytest.raises(ReturnsError, match="Insufficient data"):
            simple_returns(prices, k=1)
    
    def test_simple_returns_invalid_window(self):
        """Test with invalid window size."""
        prices = [100.0, 110.0, 105.0]
        
        # Window larger than available data
        with pytest.raises(ReturnsError, match="Window size.*larger than"):
            simple_returns(prices, k=5)
    
    def test_simple_returns_zero_price(self):
        """Test with zero price (should raise error)."""
        prices = [100.0, 0.0, 110.0]  # Zero price
        
        with pytest.raises(ReturnsError, match="Zero or negative prices"):
            simple_returns(prices, k=1)
    
    def test_simple_returns_negative_price(self):
        """Test with negative price (should raise error)."""
        prices = [100.0, -50.0, 110.0]  # Negative price
        
        with pytest.raises(ReturnsError, match="Zero or negative prices"):
            simple_returns(prices, k=1)


class TestSimpleReturnsVectorized:
    """Tests for vectorized returns calculation."""
    
    def test_simple_returns_vectorized_basic(self):
        """Test vectorized returns calculation."""
        # Price series: 100 -> 110 -> 121 -> 115.5
        prices = [100.0, 110.0, 121.0, 115.5]
        
        # Calculate all 1-day returns
        returns = simple_returns_vectorized(prices, k=1)
        
        # Should return array with 3 returns
        assert len(returns) == 3
        
        # Verify each return
        expected = [
            (110.0 / 100.0) - 1,  # +10%
            (121.0 / 110.0) - 1,  # +10%
            (115.5 / 121.0) - 1   # -4.55%
        ]
        
        for actual, exp in zip(returns, expected):
            assert abs(actual - exp) < 1e-6
    
    def test_simple_returns_vectorized_multiple_windows(self):
        """Test vectorized returns with different windows."""
        # 6 prices for testing multiple windows
        prices = [100.0, 110.0, 121.0, 115.5, 127.05, 120.0]
        
        # 1-day returns (5 calculations)
        ret_1d = simple_returns_vectorized(prices, k=1)
        assert len(ret_1d) == 5
        
        # 3-day returns (3 calculations)  
        ret_3d = simple_returns_vectorized(prices, k=3)
        assert len(ret_3d) == 3
        
        # Verify 3-day calculation
        # From 100 to 115.5 = +15.5%
        expected_3d_first = (115.5 / 100.0) - 1
        assert abs(ret_3d[0] - expected_3d_first) < 1e-6
    
    def test_simple_returns_vectorized_single_window(self):
        """Test vectorized returns with window equal to data length."""
        prices = [100.0, 120.0, 110.0]
        
        # 3-day window on 3 prices = 0 calculations (need 4 prices for 3-day return)
        returns = simple_returns_vectorized(prices, k=3)
        assert len(returns) == 0
        assert isinstance(returns, np.ndarray)
    
    def test_simple_returns_vectorized_empty_result(self):
        """Test when window is too large."""
        prices = [100.0, 110.0]  # 2 prices
        
        # 5-day window on 2 prices = 0 calculations
        returns = simple_returns_vectorized(prices, k=5)
        assert len(returns) == 0
        assert isinstance(returns, np.ndarray)
    
    def test_simple_returns_vectorized_numpy_output(self):
        """Test that output is numpy array."""
        prices = [100.0, 110.0, 121.0]
        returns = simple_returns_vectorized(prices, k=1)
        
        assert isinstance(returns, np.ndarray)
        assert returns.dtype == np.float64
