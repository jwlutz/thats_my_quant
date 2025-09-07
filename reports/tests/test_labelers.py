"""
Tests for classification labelers.
Threshold boundaries and edge cases for volatility and concentration.
"""

import pytest

# Import labelers (will be created next)
from reports.labelers import (
    classify_vol_level,
    classify_concentration,
    LabelerError
)


class TestVolatilityLabeler:
    """Tests for volatility level classification."""
    
    def test_classify_vol_level_low(self):
        """Test low volatility classification."""
        # Below 20%
        assert classify_vol_level(0.15) == "low"
        assert classify_vol_level(0.10) == "low"
        assert classify_vol_level(0.199) == "low"  # Just below threshold
    
    def test_classify_vol_level_moderate(self):
        """Test moderate volatility classification."""
        # 20% - 35%
        assert classify_vol_level(0.20) == "moderate"  # Boundary
        assert classify_vol_level(0.25) == "moderate"
        assert classify_vol_level(0.30) == "moderate"
        assert classify_vol_level(0.35) == "moderate"  # Upper boundary
    
    def test_classify_vol_level_high(self):
        """Test high volatility classification."""
        # Above 35%
        assert classify_vol_level(0.351) == "high"  # Just above threshold
        assert classify_vol_level(0.50) == "high"
        assert classify_vol_level(1.00) == "high"
    
    def test_classify_vol_level_boundary_cases(self):
        """Test exact boundary values."""
        assert classify_vol_level(0.20) == "moderate"  # Exactly 20%
        assert classify_vol_level(0.35) == "moderate"  # Exactly 35%
    
    def test_classify_vol_level_invalid_input(self):
        """Test invalid volatility inputs."""
        # Negative volatility
        with pytest.raises(LabelerError, match="Volatility must be non-negative"):
            classify_vol_level(-0.1)
        
        # None input
        with pytest.raises(LabelerError, match="Volatility cannot be None"):
            classify_vol_level(None)
        
        # Extremely high volatility (>500%)
        with pytest.raises(LabelerError, match="Unrealistic volatility"):
            classify_vol_level(5.0)


class TestConcentrationLabeler:
    """Tests for concentration level classification."""
    
    def test_classify_concentration_cr5_low(self):
        """Test low concentration via CR5."""
        conc_data = {'cr5': 0.20}  # 20% - low
        
        result = classify_concentration(conc_data)
        
        assert result['level'] == 'low'
        assert result['basis'] == 'CR5'
    
    def test_classify_concentration_cr5_moderate(self):
        """Test moderate concentration via CR5."""
        conc_data = {'cr5': 0.30}  # 30% - moderate
        
        result = classify_concentration(conc_data)
        
        assert result['level'] == 'moderate'
        assert result['basis'] == 'CR5'
    
    def test_classify_concentration_cr5_high(self):
        """Test high concentration via CR5."""
        conc_data = {'cr5': 0.50}  # 50% - high
        
        result = classify_concentration(conc_data)
        
        assert result['level'] == 'high'
        assert result['basis'] == 'CR5'
    
    def test_classify_concentration_cr5_boundaries(self):
        """Test CR5 boundary values."""
        # Exactly 25% - should be moderate
        result = classify_concentration({'cr5': 0.25})
        assert result['level'] == 'moderate'
        assert result['basis'] == 'CR5'
        
        # Exactly 40% - should be moderate
        result = classify_concentration({'cr5': 0.40})
        assert result['level'] == 'moderate'
        assert result['basis'] == 'CR5'
        
        # Just above 40%
        result = classify_concentration({'cr5': 0.401})
        assert result['level'] == 'high'
        assert result['basis'] == 'CR5'
    
    def test_classify_concentration_hhi_fallback(self):
        """Test HHI fallback when CR5 not available."""
        # Only HHI data
        conc_data = {'hhi': 0.05}  # 0.05 - low
        
        result = classify_concentration(conc_data)
        
        assert result['level'] == 'low'
        assert result['basis'] == 'HHI'
    
    def test_classify_concentration_hhi_boundaries(self):
        """Test HHI boundary values."""
        # Low: < 0.10
        result = classify_concentration({'hhi': 0.09})
        assert result['level'] == 'low'
        
        # Moderate: 0.10 - 0.18
        result = classify_concentration({'hhi': 0.10})
        assert result['level'] == 'moderate'
        
        result = classify_concentration({'hhi': 0.18})
        assert result['level'] == 'moderate'
        
        # High: > 0.18
        result = classify_concentration({'hhi': 0.19})
        assert result['level'] == 'high'
    
    def test_classify_concentration_prefer_cr5_over_hhi(self):
        """Test that CR5 is preferred when both are available."""
        conc_data = {
            'cr5': 0.30,  # Would be moderate
            'hhi': 0.05   # Would be low
        }
        
        result = classify_concentration(conc_data)
        
        # Should use CR5, not HHI
        assert result['level'] == 'moderate'
        assert result['basis'] == 'CR5'
    
    def test_classify_concentration_no_data(self):
        """Test classification with no concentration data."""
        conc_data = {}  # No CR5 or HHI
        
        result = classify_concentration(conc_data)
        
        assert result['level'] == 'unknown'
        assert result['basis'] == 'insufficient_data'
    
    def test_classify_concentration_invalid_values(self):
        """Test classification with invalid concentration values."""
        # Negative CR5
        with pytest.raises(LabelerError, match="CR5 must be between 0 and 1"):
            classify_concentration({'cr5': -0.1})
        
        # CR5 > 1
        with pytest.raises(LabelerError, match="CR5 must be between 0 and 1"):
            classify_concentration({'cr5': 1.5})
        
        # Negative HHI
        with pytest.raises(LabelerError, match="HHI must be between 0 and 1"):
            classify_concentration({'hhi': -0.05})
        
        # HHI > 1
        with pytest.raises(LabelerError, match="HHI must be between 0 and 1"):
            classify_concentration({'hhi': 1.2})


class TestLabelerIntegration:
    """Tests for labeler integration and consistency."""
    
    def test_labelers_deterministic(self):
        """Test that labelers are deterministic."""
        # Same input should always produce same output
        vol_result_1 = classify_vol_level(0.25)
        vol_result_2 = classify_vol_level(0.25)
        assert vol_result_1 == vol_result_2
        
        conc_data = {'cr5': 0.30}
        conc_result_1 = classify_concentration(conc_data)
        conc_result_2 = classify_concentration(conc_data)
        assert conc_result_1 == conc_result_2
    
    def test_labelers_comprehensive_coverage(self):
        """Test that labelers cover all possible input ranges."""
        # Test volatility across full range
        vol_test_cases = [0.05, 0.15, 0.25, 0.35, 0.45, 0.75]
        for vol in vol_test_cases:
            result = classify_vol_level(vol)
            assert result in ['low', 'moderate', 'high']
        
        # Test concentration across full range
        cr5_test_cases = [0.10, 0.25, 0.40, 0.60, 0.80]
        for cr5 in cr5_test_cases:
            result = classify_concentration({'cr5': cr5})
            assert result['level'] in ['low', 'moderate', 'high']
            assert result['basis'] == 'CR5'
    
    def test_edge_case_very_small_values(self):
        """Test classification with very small values."""
        # Very small volatility
        assert classify_vol_level(0.001) == "low"  # 0.1%
        
        # Very small concentration
        result = classify_concentration({'cr5': 0.001})
        assert result['level'] == 'low'
    
    def test_edge_case_zero_values(self):
        """Test classification with zero values."""
        # Zero volatility (constant prices)
        assert classify_vol_level(0.0) == "low"
        
        # Zero concentration (impossible but test boundary)
        result = classify_concentration({'cr5': 0.0})
        assert result['level'] == 'low'
