"""
Tests for drawdown and recovery calculation utilities.
Uses crafted series with known drawdown patterns for verification.
"""

import pytest
import numpy as np
from datetime import date, timedelta

# Import drawdown utilities (will be created next)
from analysis.calculations.drawdown import (
    drawdown_stats,
    rolling_drawdown,
    DrawdownError
)


class TestDrawdownStats:
    """Tests for drawdown_stats function."""
    
    def test_drawdown_stats_simple_pattern(self):
        """Test drawdown with clear peak-trough-recovery pattern."""
        # Crafted series: 100 -> 120 (peak) -> 90 (trough) -> 125 (recovery)
        prices = [100.0, 110.0, 120.0, 110.0, 90.0, 100.0, 115.0, 125.0]
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(8)]
        
        result = drawdown_stats(prices, dates)
        
        # Max drawdown: 120 -> 90 = -25%
        expected_dd = (90.0 / 120.0) - 1  # -0.25
        assert abs(result['max_drawdown_pct'] - expected_dd) < 1e-6
        
        # Peak should be at index 2 (120.0)
        assert result['peak_date'] == dates[2]  # 2025-08-03
        
        # Trough should be at index 4 (90.0)
        assert result['trough_date'] == dates[4]  # 2025-08-05
        
        # Recovery should be at index 7 (125.0 > 120.0)
        assert result['recovery_date'] == dates[7]  # 2025-08-08
        
        # Drawdown period: 2 days (peak to trough)
        assert result['drawdown_days'] == 2
        
        # Recovery period: 3 days (trough to recovery)
        assert result['recovery_days'] == 3
    
    def test_drawdown_stats_no_recovery(self):
        """Test drawdown with no recovery."""
        # Series: 100 -> 120 -> 80 (never recovers)
        prices = [100.0, 110.0, 120.0, 100.0, 80.0, 85.0, 90.0]
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(7)]
        
        result = drawdown_stats(prices, dates)
        
        # Max drawdown: 120 -> 80 = -33.33%
        expected_dd = (80.0 / 120.0) - 1
        assert abs(result['max_drawdown_pct'] - expected_dd) < 1e-6
        
        # Should have peak and trough
        assert result['peak_date'] == dates[2]  # 120.0
        assert result['trough_date'] == dates[4]  # 80.0
        
        # No recovery
        assert result['recovery_date'] is None
        assert result['recovery_days'] is None
        
        # Drawdown days: 2 (peak to trough)
        assert result['drawdown_days'] == 2
    
    def test_drawdown_stats_no_drawdown(self):
        """Test series with no significant drawdown (always rising)."""
        # Monotonically increasing
        prices = [100.0, 105.0, 110.0, 115.0, 120.0]
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(5)]
        
        result = drawdown_stats(prices, dates)
        
        # Should have minimal drawdown (0 or very small)
        assert result['max_drawdown_pct'] >= -0.001  # Less than 0.1%
        
        # If there's any drawdown, it should be tiny
        if result['max_drawdown_pct'] < 0:
            assert abs(result['max_drawdown_pct']) < 0.05  # Less than 5%
    
    def test_drawdown_stats_multiple_drawdowns(self):
        """Test series with multiple drawdowns (should find largest)."""
        # Two drawdowns: 100->120->110 (-8.33%) and 110->130->95 (-26.92%)
        prices = [100.0, 120.0, 110.0, 115.0, 130.0, 95.0, 100.0, 135.0]
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(8)]
        
        result = drawdown_stats(prices, dates)
        
        # Should find the larger drawdown: 130 -> 95 = -26.92%
        expected_dd = (95.0 / 130.0) - 1
        assert abs(result['max_drawdown_pct'] - expected_dd) < 1e-6
        
        # Peak should be 130 (index 4), trough should be 95 (index 5)
        assert result['peak_date'] == dates[4]
        assert result['trough_date'] == dates[5]
        
        # Recovery at 135 (index 7)
        assert result['recovery_date'] == dates[7]
    
    def test_drawdown_stats_insufficient_data(self):
        """Test with insufficient data."""
        prices = [100.0]  # Only 1 price
        dates = [date(2025, 8, 1)]
        
        with pytest.raises(DrawdownError, match="Insufficient data"):
            drawdown_stats(prices, dates)
    
    def test_drawdown_stats_mismatched_lengths(self):
        """Test with mismatched prices and dates."""
        prices = [100.0, 110.0, 120.0]
        dates = [date(2025, 8, 1), date(2025, 8, 2)]  # Only 2 dates
        
        with pytest.raises(DrawdownError, match="Prices and dates.*same length"):
            drawdown_stats(prices, dates)
    
    def test_drawdown_stats_invalid_prices(self):
        """Test with invalid prices."""
        prices = [100.0, 0.0, 110.0]  # Zero price
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(3)]
        
        with pytest.raises(DrawdownError, match="Zero or negative prices"):
            drawdown_stats(prices, dates)


class TestRollingDrawdown:
    """Tests for rolling drawdown calculation."""
    
    def test_rolling_drawdown_basic(self):
        """Test rolling drawdown calculation."""
        # Series with clear drawdown pattern
        prices = [100.0, 110.0, 120.0, 100.0, 80.0, 90.0, 100.0, 130.0]
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(8)]
        
        # 5-day rolling drawdown
        rolling_dd = rolling_drawdown(prices, dates, window=5)
        
        # Should return 4 drawdown stats (8 - 5 + 1)
        assert len(rolling_dd) == 4
        
        # Each should be a drawdown stats dict
        for dd_stat in rolling_dd:
            required_keys = {
                'max_drawdown_pct', 'peak_date', 'trough_date', 
                'recovery_date', 'drawdown_days', 'recovery_days'
            }
            assert required_keys.issubset(dd_stat.keys())
    
    def test_rolling_drawdown_insufficient_data(self):
        """Test rolling drawdown with insufficient data."""
        prices = [100.0, 110.0]  # Only 2 prices
        dates = [date(2025, 8, 1), date(2025, 8, 2)]
        
        with pytest.raises(DrawdownError, match="Insufficient data"):
            rolling_drawdown(prices, dates, window=5)  # Need 5 prices
    
    def test_rolling_drawdown_minimum_window(self):
        """Test rolling drawdown with minimum window."""
        prices = [100.0, 120.0, 90.0, 110.0]
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(4)]
        
        # 3-day rolling windows
        rolling_dd = rolling_drawdown(prices, dates, window=3)
        
        assert len(rolling_dd) == 2  # 4 - 3 + 1
        
        # First window: [100, 120, 90] - drawdown from 120 to 90
        first_dd = rolling_dd[0]
        expected_dd = (90.0 / 120.0) - 1
        assert abs(first_dd['max_drawdown_pct'] - expected_dd) < 1e-6


class TestDrawdownIntegration:
    """Integration tests for drawdown calculations."""
    
    def test_drawdown_realistic_stock_pattern(self):
        """Test with realistic stock price pattern."""
        # Simulate a stock crash and recovery
        # Start at 200, rise to 250, crash to 150, recover to 275
        prices = [
            200.0, 210.0, 225.0, 240.0, 250.0,  # Rise to peak
            245.0, 230.0, 200.0, 175.0, 150.0,  # Crash to trough  
            160.0, 180.0, 200.0, 220.0, 240.0,  # Recovery
            255.0, 275.0  # Full recovery + new high
        ]
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(17)]
        
        result = drawdown_stats(prices, dates)
        
        # Max drawdown: 250 -> 150 = -40%
        expected_dd = (150.0 / 250.0) - 1
        assert abs(result['max_drawdown_pct'] - expected_dd) < 1e-6
        
        # Peak at 250 (index 4)
        assert result['peak_date'] == dates[4]
        
        # Trough at 150 (index 9)  
        assert result['trough_date'] == dates[9]
        
        # Recovery when price exceeds 250 (at 275, index 16)
        # Note: recovery is when price first exceeds peak (255 > 250 at index 15)
        assert result['recovery_date'] == dates[15]
        
        # Drawdown: 5 days (index 4 to 9)
        assert result['drawdown_days'] == 5
        
        # Recovery: 6 days (index 9 to 15)
        assert result['recovery_days'] == 6
    
    def test_drawdown_edge_case_flat_peak(self):
        """Test drawdown with flat peak period."""
        # Flat peak: 100 -> 120 -> 120 -> 120 -> 90 -> 125
        prices = [100.0, 120.0, 120.0, 120.0, 90.0, 125.0]
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(6)]
        
        result = drawdown_stats(prices, dates)
        
        # Max drawdown: 120 -> 90 = -25%
        expected_dd = (90.0 / 120.0) - 1
        assert abs(result['max_drawdown_pct'] - expected_dd) < 1e-6
        
        # Peak should be first occurrence of 120 (index 1)
        assert result['peak_date'] == dates[1]
        
        # Trough at 90 (index 4)
        assert result['trough_date'] == dates[4]
        
        # Recovery at 125 (index 5)
        assert result['recovery_date'] == dates[5]
    
    def test_drawdown_end_in_drawdown(self):
        """Test series that ends while in drawdown."""
        # 100 -> 120 -> 80 (ends here, no recovery)
        prices = [100.0, 110.0, 120.0, 110.0, 95.0, 80.0]
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(6)]
        
        result = drawdown_stats(prices, dates)
        
        # Max drawdown: 120 -> 80 = -33.33%
        expected_dd = (80.0 / 120.0) - 1
        assert abs(result['max_drawdown_pct'] - expected_dd) < 1e-6
        
        # Should have peak and trough
        assert result['peak_date'] == dates[2]
        assert result['trough_date'] == dates[5]
        
        # No recovery (series ends in drawdown)
        assert result['recovery_date'] is None
        assert result['recovery_days'] is None
        
        # Drawdown days: 3 (index 2 to 5)
        assert result['drawdown_days'] == 3
    
    def test_drawdown_minimum_data(self):
        """Test with minimum required data."""
        prices = [100.0, 95.0, 90.0]  # 3 prices, clear drawdown
        dates = [date(2025, 8, 1), date(2025, 8, 2), date(2025, 8, 3)]
        
        result = drawdown_stats(prices, dates)
        
        # Drawdown from 100 to 90 = -10%
        expected_dd = (90.0 / 100.0) - 1
        assert abs(result['max_drawdown_pct'] - expected_dd) < 1e-6
        
        assert result['peak_date'] == dates[0]
        assert result['trough_date'] == dates[2]
        assert result['recovery_date'] is None  # No recovery
    
    def test_drawdown_all_time_high_end(self):
        """Test series ending at all-time high."""
        prices = [100.0, 90.0, 95.0, 110.0, 130.0]  # Ends at ATH
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(5)]
        
        result = drawdown_stats(prices, dates)
        
        # Should find the 100 -> 90 drawdown
        expected_dd = (90.0 / 100.0) - 1  # -10%
        assert abs(result['max_drawdown_pct'] - expected_dd) < 1e-6
        
        # Recovery should be when price exceeds 100 (at 110, index 3)
        assert result['recovery_date'] == dates[3]


class TestRollingDrawdown:
    """Tests for rolling drawdown calculation."""
    
    def test_rolling_drawdown_basic(self):
        """Test rolling drawdown over multiple windows."""
        # 8 prices for rolling 5-day windows
        prices = [100.0, 120.0, 90.0, 110.0, 80.0, 100.0, 130.0, 95.0]
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(8)]
        
        rolling_dd = rolling_drawdown(prices, dates, window=5)
        
        # Should return 4 drawdown calculations (8 - 5 + 1)
        assert len(rolling_dd) == 4
        
        # Each should be valid drawdown stats
        for dd_stat in rolling_dd:
            assert isinstance(dd_stat['max_drawdown_pct'], float)
            assert dd_stat['max_drawdown_pct'] <= 0  # Should be negative or zero
            assert isinstance(dd_stat['peak_date'], date)
            assert isinstance(dd_stat['trough_date'], date)
    
    def test_rolling_drawdown_window_equals_data(self):
        """Test rolling drawdown with window equal to data length."""
        prices = [100.0, 120.0, 80.0, 110.0, 90.0]
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(5)]
        
        rolling_dd = rolling_drawdown(prices, dates, window=5)
        
        # Should return 1 calculation
        assert len(rolling_dd) == 1
        
        # Should be same as drawdown_stats for full series
        full_stats = drawdown_stats(prices, dates)
        assert abs(rolling_dd[0]['max_drawdown_pct'] - full_stats['max_drawdown_pct']) < 1e-6


class TestDrawdownEdgeCases:
    """Tests for edge cases in drawdown calculation."""
    
    def test_drawdown_single_day_drop_recovery(self):
        """Test single-day drawdown with immediate recovery."""
        # 100 -> 120 -> 80 -> 125 (immediate recovery)
        prices = [100.0, 120.0, 80.0, 125.0]
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(4)]
        
        result = drawdown_stats(prices, dates)
        
        # Drawdown: 120 -> 80 = -33.33%
        expected_dd = (80.0 / 120.0) - 1
        assert abs(result['max_drawdown_pct'] - expected_dd) < 1e-6
        
        # Drawdown: 0 days (same day peak to trough)
        assert result['drawdown_days'] == 1  # Peak day to trough day
        
        # Recovery: 1 day (trough to recovery)
        assert result['recovery_days'] == 1
    
    def test_drawdown_identical_consecutive_prices(self):
        """Test with identical consecutive prices."""
        prices = [100.0, 100.0, 120.0, 120.0, 90.0, 90.0, 125.0]
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(7)]
        
        result = drawdown_stats(prices, dates)
        
        # Should handle flat periods correctly
        # Peak at first 120 (index 2)
        assert result['peak_date'] == dates[2]
        
        # Trough at first 90 (index 4)  
        assert result['trough_date'] == dates[4]
        
        # Recovery at 125 (index 6)
        assert result['recovery_date'] == dates[6]
    
    def test_drawdown_zero_drawdown(self):
        """Test with exactly zero drawdown (constant prices)."""
        prices = [100.0, 100.0, 100.0, 100.0]
        dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(4)]
        
        result = drawdown_stats(prices, dates)
        
        # Should have zero drawdown
        assert result['max_drawdown_pct'] == 0.0
        
        # Peak and trough should be same (first date)
        assert result['peak_date'] == dates[0]
        assert result['trough_date'] == dates[0]
        
        # Immediate "recovery" (no actual drawdown)
        assert result['recovery_date'] == dates[0]
        assert result['drawdown_days'] == 0
        assert result['recovery_days'] == 0
