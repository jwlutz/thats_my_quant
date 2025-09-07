"""
Tests for executive summary skeleton builder.
Fixture → exact expected skeleton string.
"""

import pytest
import json
from pathlib import Path

# Import skeleton builder (will be created next)
from reports.skeleton_builder import (
    build_exec_summary_skeleton,
    SkeletonBuilderError
)


def load_fixture(filename):
    """Load fixture from golden directory."""
    fixture_path = Path(__file__).parent.parent.parent / 'tests/fixtures/golden' / filename
    with open(fixture_path, 'r') as f:
        return json.load(f)


class TestSkeletonBuilder:
    """Tests for executive summary skeleton generation."""
    
    def test_build_exec_summary_skeleton_complete_data(self):
        """Test skeleton building with complete v2 data."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        
        skeleton = build_exec_summary_skeleton(v2_metrics)
        
        # Should be substantial text
        assert len(skeleton) > 100
        assert isinstance(skeleton, str)
        
        # Should contain key elements from v2 data
        ticker = v2_metrics['meta']['ticker']
        assert ticker in skeleton
        
        # Should contain formatted values (not raw)
        price = v2_metrics['price']
        current_display = price['current']['display']
        assert current_display in skeleton
        
        # Should contain volatility with window
        vol_display = price['volatility']['display']
        vol_window = price['volatility']['window_display']
        if vol_display != "Not available":
            assert vol_display in skeleton
            assert vol_window in skeleton
        
        # Should contain drawdown information
        dd_display = price['drawdown']['max_dd_display']
        if dd_display != "Not available":
            assert dd_display in skeleton
    
    def test_build_exec_summary_skeleton_word_count(self):
        """Test that skeleton falls within word count bounds."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        
        skeleton = build_exec_summary_skeleton(v2_metrics)
        
        word_count = len(skeleton.split())
        assert 120 <= word_count <= 180, f"Skeleton word count {word_count} outside bounds (120-180)"
    
    def test_build_exec_summary_skeleton_missing_volatility(self):
        """Test skeleton with missing volatility data."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        
        # Remove volatility data
        v2_metrics['price']['volatility']['display'] = "Not available"
        v2_metrics['price']['volatility']['level'] = "unknown"
        
        skeleton = build_exec_summary_skeleton(v2_metrics)
        
        # Should handle missing data gracefully
        assert "Volatility data not available" in skeleton or "volatility not available" in skeleton.lower()
        assert len(skeleton.split()) >= 100  # Should still be substantial
    
    def test_build_exec_summary_skeleton_missing_13f(self):
        """Test skeleton with no institutional data."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        
        # Remove institutional data
        del v2_metrics['ownership_13f']
        
        skeleton = build_exec_summary_skeleton(v2_metrics)
        
        # Should handle missing 13F data
        assert "Institutional ownership data not available" in skeleton or "institutional data not available" in skeleton.lower()
        
        # Should still mention price metrics
        assert v2_metrics['price']['current']['display'] in skeleton
    
    def test_build_exec_summary_skeleton_recovery_status(self):
        """Test recovery status handling in skeleton."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        
        # Test with recovery
        drawdown = v2_metrics['price']['drawdown']
        if drawdown['recovered']:
            skeleton = build_exec_summary_skeleton(v2_metrics)
            assert 'recovered' in skeleton.lower()
            if drawdown['recovery_date_display']:
                assert drawdown['recovery_date_display'] in skeleton
        
        # Test without recovery
        v2_metrics['price']['drawdown']['recovered'] = False
        v2_metrics['price']['drawdown']['recovery_date'] = None
        v2_metrics['price']['drawdown']['recovery_status'] = "unrecovered as of September 6, 2025"
        
        skeleton_no_recovery = build_exec_summary_skeleton(v2_metrics)
        assert 'unrecovered' in skeleton_no_recovery.lower()
    
    def test_build_exec_summary_skeleton_concentration_mention(self):
        """Test that concentration level is mentioned correctly."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        
        skeleton = build_exec_summary_skeleton(v2_metrics)
        
        ownership = v2_metrics.get('ownership_13f')
        if ownership:
            concentration = ownership['concentration']
            level = concentration['level']
            basis = concentration['basis']
            
            # Should mention level and basis
            assert level in skeleton.lower()
            assert basis in skeleton
    
    def test_build_exec_summary_skeleton_no_speculation(self):
        """Test that skeleton contains no speculative language."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        
        skeleton = build_exec_summary_skeleton(v2_metrics)
        
        # Prohibited speculative words
        prohibited = ['will', 'should', 'expect', 'likely', 'probably', 'may', 'might', 'could', 'target', 'forecast']
        
        skeleton_lower = skeleton.lower()
        found_prohibited = [word for word in prohibited if word in skeleton_lower]
        
        assert found_prohibited == [], f"Speculative words found: {found_prohibited}"
    
    def test_build_exec_summary_skeleton_data_grounding(self):
        """Test that all skeleton content is grounded in v2 data."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        
        skeleton = build_exec_summary_skeleton(v2_metrics)
        
        # Extract audit index for verification
        audit_index = v2_metrics['audit_index']
        
        # All percentages in skeleton should be in audit index
        import re
        found_percentages = re.findall(r'-?\d+\.?\d*%', skeleton)
        audit_percentages = audit_index['percent_strings']
        
        for pct in found_percentages:
            assert pct in audit_percentages, f"Percentage {pct} not in audit index"
        
        # All currency amounts should be in audit index
        found_currency = re.findall(r'\$\d+\.?\d*[BMK]?', skeleton)
        audit_currency = audit_index['currency_strings']
        
        for curr in found_currency:
            assert curr in audit_currency, f"Currency {curr} not in audit index"
    
    def test_build_exec_summary_skeleton_minimal_data(self):
        """Test skeleton with minimal data availability."""
        # Create minimal v2 metrics
        minimal_v2 = {
            'meta': {
                'ticker': 'TEST',
                'schema_version': '2.0.0'
            },
            'price': {
                'current': {
                    'value': 100.0,
                    'display': '$100.00',
                    'date_display': 'September 6, 2025'
                },
                'returns': {
                    'raw': {'1D': 0.01},
                    'display': {'1D': '1.0%'}
                },
                'volatility': {
                    'display': 'Not available',
                    'level': 'unknown'
                },
                'drawdown': {
                    'max_dd_display': 'Not available'
                }
            },
            'audit_index': {
                'percent_strings': ['1.0%'],
                'currency_strings': ['$100.00'],
                'dates': ['September 6, 2025'],
                'labels': ['unknown'],
                'numbers': [100.0, 1.0],
                'windows': []
            }
        }
        
        skeleton = build_exec_summary_skeleton(minimal_v2)
        
        # Should handle minimal data gracefully
        assert 'TEST' in skeleton
        assert '$100.00' in skeleton
        assert '1.0%' in skeleton
        assert 'not available' in skeleton.lower()
        
        # Should still be readable paragraph
        word_count = len(skeleton.split())
        assert word_count >= 50  # At least some content
