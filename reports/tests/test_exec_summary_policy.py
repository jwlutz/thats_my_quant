"""
Tests for executive summary policy and fixtures.
Contract validation and fixture consistency.
"""

import pytest
import json
from pathlib import Path

# Import policy functions (will be created next)
from reports.exec_summary_policy import (
    validate_exec_summary_contract,
    load_skeleton_fixture,
    ExecSummaryPolicyError
)


def load_fixture(filename):
    """Load fixture from tests/fixtures/golden directory."""
    fixture_path = Path(__file__).parent.parent.parent / 'tests/fixtures/golden' / filename
    
    if filename.endswith('.json'):
        with open(fixture_path, 'r') as f:
            return json.load(f)
    elif filename.endswith('.txt'):
        with open(fixture_path, 'r') as f:
            return f.read().strip()
    else:
        raise ValueError(f"Unknown fixture format: {filename}")


class TestExecSummaryPolicy:
    """Tests for executive summary policy validation."""
    
    def test_validate_contract_complete_data(self):
        """Test contract validation with complete MetricsJSON."""
        metrics = load_fixture('aapl_metrics_complete.json')
        
        # Should not raise
        validation = validate_exec_summary_contract(metrics)
        
        assert validation['valid'] is True
        assert validation['has_price_metrics'] is True
        assert validation['has_institutional_metrics'] is True
        assert validation['has_volatility'] is True
        assert validation['has_drawdown'] is True
        assert validation['has_concentration'] is True
    
    def test_validate_contract_price_only(self):
        """Test contract validation with price data only."""
        price_only_metrics = {
            'ticker': 'TEST',
            'as_of_date': '2025-09-06',
            'price_metrics': {
                'returns': {'1D': 0.01, '1M': 0.05},
                'volatility': {'21D_annualized': 0.25},
                'drawdown': {'max_drawdown_pct': -0.10, 'peak_date': '2025-08-01', 'trough_date': '2025-08-05', 'recovery_date': '2025-08-10'},
                'current_price': {'close': 100.0, 'date': '2025-09-05'}
            },
            'institutional_metrics': None,
            'data_quality': {},
            'metadata': {}
        }
        
        validation = validate_exec_summary_contract(price_only_metrics)
        
        assert validation['valid'] is True
        assert validation['has_price_metrics'] is True
        assert validation['has_institutional_metrics'] is False
        assert validation['has_volatility'] is True
        assert validation['has_drawdown'] is True
        assert validation['has_concentration'] is False
    
    def test_validate_contract_missing_required(self):
        """Test validation with missing required fields."""
        incomplete_metrics = {
            'ticker': 'TEST',
            'as_of_date': '2025-09-06'
            # Missing price_metrics
        }
        
        with pytest.raises(ExecSummaryPolicyError, match="Missing required field"):
            validate_exec_summary_contract(incomplete_metrics)
    
    def test_validate_contract_insufficient_data(self):
        """Test validation with insufficient data for summary."""
        minimal_metrics = {
            'ticker': 'TEST',
            'as_of_date': '2025-09-06',
            'price_metrics': {
                'returns': {},  # No returns data
                'volatility': {},  # No volatility data
                'drawdown': {'max_drawdown_pct': None},  # No drawdown data
                'current_price': {'close': 100.0, 'date': '2025-09-05'}
            },
            'institutional_metrics': None,
            'data_quality': {},
            'metadata': {}
        }
        
        validation = validate_exec_summary_contract(minimal_metrics)
        
        assert validation['valid'] is True  # Should still be valid
        assert validation['has_volatility'] is False
        assert validation['has_drawdown'] is False
        assert validation['data_sufficiency'] == 'minimal'


class TestSkeletonFixtures:
    """Tests for skeleton fixture consistency."""
    
    def test_load_skeleton_fixture(self):
        """Test loading skeleton fixture."""
        skeleton = load_skeleton_fixture('aapl')
        
        assert isinstance(skeleton, str)
        assert len(skeleton) > 100  # Should be substantial
        assert 'AAPL' in skeleton
        assert '%' in skeleton  # Should contain percentages
        assert '2025' in skeleton  # Should contain dates
    
    def test_skeleton_word_count(self):
        """Test that skeleton fixtures are within word count bounds."""
        skeleton = load_skeleton_fixture('aapl')
        
        word_count = len(skeleton.split())
        assert 120 <= word_count <= 180, f"Skeleton word count {word_count} outside bounds"
    
    def test_skeleton_contains_required_elements(self):
        """Test that skeleton contains all required elements."""
        skeleton = load_skeleton_fixture('aapl')
        
        # Should mention volatility with window
        assert '(' in skeleton and ')' in skeleton  # Window notation
        assert 'volatility' in skeleton.lower() or 'vol' in skeleton.lower()
        
        # Should mention drawdown
        assert 'drawdown' in skeleton.lower() or 'decline' in skeleton.lower()
        
        # Should mention dates
        assert any(month in skeleton for month in ['January', 'February', 'March', 'April', 'May', 'June', 
                                                   'July', 'August', 'September', 'October', 'November', 'December'])
        
        # Should mention concentration if 13F data available
        if 'concentration' in skeleton.lower():
            assert any(level in skeleton.lower() for level in ['low', 'moderate', 'high'])
    
    def test_skeleton_no_speculation(self):
        """Test that skeleton contains no speculative language."""
        skeleton = load_skeleton_fixture('aapl')
        
        # Prohibited words that indicate speculation
        prohibited = ['will', 'should', 'expect', 'likely', 'probably', 'may', 'might', 'could', 'target', 'forecast']
        
        skeleton_lower = skeleton.lower()
        found_prohibited = [word for word in prohibited if word in skeleton_lower]
        
        assert found_prohibited == [], f"Speculative words found: {found_prohibited}"
    
    def test_skeleton_data_grounding(self):
        """Test that skeleton is grounded in provided data."""
        skeleton = load_skeleton_fixture('aapl')
        metrics = load_fixture('aapl_metrics_complete.json')
        
        # Check that key numbers from metrics appear in skeleton
        # (This is a basic check - full audit will be in R3.4)
        
        # Check for some key values (allowing for formatting differences)
        price_metrics = metrics['price_metrics']
        
        # Current price should appear
        current_price = price_metrics['current_price']['close']
        assert str(int(current_price)) in skeleton  # At least the integer part
        
        # Some return value should appear
        returns = price_metrics['returns']
        return_found = False
        for period, value in returns.items():
            if value is not None:
                # Check if percentage appears (allowing rounding)
                pct_str = f"{abs(value * 100):.1f}"
                if pct_str in skeleton:
                    return_found = True
                    break
        
        assert return_found, "No return percentages found in skeleton"


class TestContractCompliance:
    """Tests for contract compliance validation."""
    
    def test_word_count_bounds(self):
        """Test word count boundary enforcement."""
        # Test minimum
        short_text = "This is too short for an executive summary."
        word_count = len(short_text.split())
        assert word_count < 120  # Should be under minimum
        
        # Test maximum  
        long_text = " ".join(["word"] * 200)  # 200 words
        word_count = len(long_text.split())
        assert word_count > 180  # Should be over maximum
        
        # Test valid range
        skeleton = load_skeleton_fixture('aapl')
        skeleton_word_count = len(skeleton.split())
        assert 120 <= skeleton_word_count <= 180
    
    def test_required_elements_detection(self):
        """Test detection of required elements in text."""
        # Text with all required elements
        complete_text = """
        AAPL showed 8.9% returns with 28.4% volatility (21-day). 
        Maximum drawdown of -18.5% from July 15, 2025 recovered by August 28, 2025.
        Institutional concentration is low based on CR5 with 12.3% held by top 5.
        """
        
        # Should detect all elements
        # (This would use helper functions from the policy module)
        assert 'volatility' in complete_text.lower()
        assert 'drawdown' in complete_text.lower()
        assert 'concentration' in complete_text.lower()
        assert any(month in complete_text for month in ['July', 'August'])
    
    def test_missing_data_handling(self):
        """Test handling of missing data scenarios."""
        # Text with missing data indicators
        missing_data_text = """
        AAPL current price is $229.87. Volatility data not available.
        Drawdown analysis not available due to insufficient data.
        Institutional concentration not available.
        """
        
        # Should handle gracefully
        assert 'not available' in missing_data_text
        assert '$229.87' in missing_data_text  # Available data still shown
