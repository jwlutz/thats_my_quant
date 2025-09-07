"""
Tests for 13F concentration calculation utilities.
Uses tiny dict fixtures where concentration ratios are easy to verify by hand.
"""

import pytest
import math

# Import concentration utilities (will be created next)
from analysis.calculations.concentration import (
    concentration_ratios,
    herfindahl_index,
    calculate_concentration_metrics,
    ConcentrationError
)


class TestConcentrationRatios:
    """Tests for concentration ratio calculation."""
    
    def test_concentration_ratios_basic(self):
        """Test concentration ratios with simple example."""
        # 4 holders: 50%, 30%, 15%, 5%
        value_by_holder = {
            'Holder A': 50.0,
            'Holder B': 30.0, 
            'Holder C': 15.0,
            'Holder D': 5.0
        }
        
        result = concentration_ratios(value_by_holder)
        
        # Total value: 100
        # CR1: 50/100 = 0.5
        # CR5: (50+30+15+5)/100 = 1.0 (all holders)
        # CR10: 1.0 (only 4 holders)
        
        assert abs(result['cr1'] - 0.5) < 1e-6
        assert abs(result['cr5'] - 1.0) < 1e-6
        assert abs(result['cr10'] - 1.0) < 1e-6
    
    def test_concentration_ratios_single_holder(self):
        """Test with single holder (100% concentration)."""
        value_by_holder = {'Only Holder': 1000000.0}
        
        result = concentration_ratios(value_by_holder)
        
        # All ratios should be 1.0 (100%)
        assert result['cr1'] == 1.0
        assert result['cr5'] == 1.0  
        assert result['cr10'] == 1.0
    
    def test_concentration_ratios_equal_holders(self):
        """Test with equal-sized holders."""
        # 5 holders with equal 20% each
        value_by_holder = {
            f'Holder {i}': 20.0 for i in range(5)
        }
        
        result = concentration_ratios(value_by_holder)
        
        # CR1: 20/100 = 0.2
        # CR5: 100/100 = 1.0 (all 5 holders)
        # CR10: 1.0 (only 5 holders exist)
        
        assert abs(result['cr1'] - 0.2) < 1e-6
        assert abs(result['cr5'] - 1.0) < 1e-6
        assert abs(result['cr10'] - 1.0) < 1e-6
    
    def test_concentration_ratios_many_holders(self):
        """Test with more than 10 holders."""
        # 15 holders: first has 40%, others have 4% each
        value_by_holder = {'Big Holder': 40.0}
        for i in range(14):
            value_by_holder[f'Small Holder {i}'] = 4.0
        
        # Total: 40 + (14 * 4) = 96
        
        result = concentration_ratios(value_by_holder)
        
        # CR1: 40/96 ≈ 0.4167
        assert abs(result['cr1'] - (40.0/96.0)) < 1e-6
        
        # CR5: (40 + 4*4)/96 = 56/96 ≈ 0.5833
        assert abs(result['cr5'] - (56.0/96.0)) < 1e-6
        
        # CR10: (40 + 4*9)/96 = 76/96 ≈ 0.7917
        assert abs(result['cr10'] - (76.0/96.0)) < 1e-6
    
    def test_concentration_ratios_empty_dict(self):
        """Test with empty holders dictionary."""
        with pytest.raises(ConcentrationError, match="No holders provided"):
            concentration_ratios({})
    
    def test_concentration_ratios_zero_values(self):
        """Test with zero or negative values."""
        value_by_holder = {'Holder A': 100.0, 'Holder B': 0.0, 'Holder C': -50.0}
        
        with pytest.raises(ConcentrationError, match="Non-positive values"):
            concentration_ratios(value_by_holder)


class TestHerfindalIndex:
    """Tests for Herfindahl-Hirschman Index calculation."""
    
    def test_hhi_basic(self):
        """Test HHI with known values."""
        # 4 holders: 50%, 30%, 15%, 5%
        # HHI = 0.5² + 0.3² + 0.15² + 0.05² = 0.25 + 0.09 + 0.0225 + 0.0025 = 0.365
        value_by_holder = {
            'Holder A': 50.0,
            'Holder B': 30.0,
            'Holder C': 15.0, 
            'Holder D': 5.0
        }
        
        hhi = herfindahl_index(value_by_holder)
        
        expected = 0.5**2 + 0.3**2 + 0.15**2 + 0.05**2
        assert abs(hhi - expected) < 1e-6
    
    def test_hhi_perfect_competition(self):
        """Test HHI with many equal holders (low concentration)."""
        # 10 equal holders (10% each)
        # HHI = 10 * (0.1)² = 10 * 0.01 = 0.1
        value_by_holder = {f'Holder {i}': 10.0 for i in range(10)}
        
        hhi = herfindahl_index(value_by_holder)
        
        expected = 10 * (0.1)**2
        assert abs(hhi - expected) < 1e-6
    
    def test_hhi_monopoly(self):
        """Test HHI with single holder (maximum concentration)."""
        value_by_holder = {'Monopoly Holder': 100.0}
        
        hhi = herfindahl_index(value_by_holder)
        
        # HHI = 1² = 1.0 (maximum concentration)
        assert hhi == 1.0
    
    def test_hhi_duopoly(self):
        """Test HHI with two equal holders."""
        # 50%-50% split
        # HHI = 0.5² + 0.5² = 0.25 + 0.25 = 0.5
        value_by_holder = {'Holder A': 50.0, 'Holder B': 50.0}
        
        hhi = herfindahl_index(value_by_holder)
        
        assert abs(hhi - 0.5) < 1e-6


class TestConcentrationIntegration:
    """Integration tests for concentration metrics."""
    
    def test_calculate_concentration_metrics_complete(self):
        """Test complete concentration metrics calculation."""
        # Realistic 13F data
        value_by_holder = {
            'VANGUARD GROUP INC': 45000000000.0,      # 45%
            'BLACKROCK INC': 30000000000.0,           # 30%
            'STATE STREET CORP': 15000000000.0,       # 15%
            'FIDELITY': 5000000000.0,                 # 5%
            'BERKSHIRE HATHAWAY INC': 3000000000.0,   # 3%
            'SMALL FUND': 2000000000.0                # 2%
        }
        # Total: 100B
        
        result = calculate_concentration_metrics(value_by_holder)
        
        # Verify all metrics present
        required_keys = {'cr1', 'cr5', 'cr10', 'hhi', 'total_value', 'num_holders'}
        assert required_keys.issubset(result.keys())
        
        # CR1: 45B/100B = 0.45
        assert abs(result['cr1'] - 0.45) < 1e-6
        
        # CR5: (45+30+15+5+3)/100 = 98/100 = 0.98
        assert abs(result['cr5'] - 0.98) < 1e-6
        
        # CR10: 100/100 = 1.0 (only 6 holders)
        assert abs(result['cr10'] - 1.0) < 1e-6
        
        # HHI: 0.45² + 0.3² + 0.15² + 0.05² + 0.03² + 0.02²
        expected_hhi = 0.45**2 + 0.3**2 + 0.15**2 + 0.05**2 + 0.03**2 + 0.02**2
        assert abs(result['hhi'] - expected_hhi) < 1e-6
        
        # Metadata
        assert result['total_value'] == 100000000000.0
        assert result['num_holders'] == 6
    
    def test_calculate_concentration_metrics_insufficient_data(self):
        """Test with insufficient 13F data."""
        # Empty or invalid data
        result = calculate_concentration_metrics({})
        
        # Should return None for all metrics
        assert result['cr1'] is None
        assert result['cr5'] is None
        assert result['cr10'] is None
        assert result['hhi'] is None
        assert result['total_value'] == 0.0
        assert result['num_holders'] == 0
    
    def test_concentration_metrics_real_world_bounds(self):
        """Test that metrics fall within expected real-world bounds."""
        # Typical institutional ownership pattern
        value_by_holder = {
            'Large Institution': 1000000000.0,    # $1B
            'Medium Fund': 500000000.0,           # $500M
            'Small Fund': 100000000.0             # $100M
        }
        
        result = calculate_concentration_metrics(value_by_holder)
        
        # All concentration ratios should be 0-1
        assert 0 <= result['cr1'] <= 1
        assert 0 <= result['cr5'] <= 1
        assert 0 <= result['cr10'] <= 1
        
        # HHI should be 0-1
        assert 0 <= result['hhi'] <= 1
        
        # CR ratios should be monotonically increasing
        assert result['cr1'] <= result['cr5'] <= result['cr10']
