"""
Tests for v1→v2 builder - convert existing MetricsJSON to Enhanced v2.
Fixture v1 → expected v2 exactly.
"""

import pytest
import json
from pathlib import Path

# Import builder (will be created next)
from reports.v1_to_v2_builder import (
    build_enhanced_metrics_v2,
    V1ToV2BuilderError
)


def load_fixture(filename):
    """Load fixture from golden directory."""
    fixture_path = Path(__file__).parent.parent.parent / 'tests/fixtures/golden' / filename
    with open(fixture_path, 'r') as f:
        return json.load(f)


class TestV1ToV2Builder:
    """Tests for v1 to v2 conversion."""
    
    def test_build_enhanced_metrics_v2_complete(self):
        """Test complete v1 to v2 conversion."""
        v1_metrics = load_fixture('aapl_metrics_complete.json')
        
        v2_metrics = build_enhanced_metrics_v2(v1_metrics)
        
        # Should have v2 structure
        assert v2_metrics['meta']['schema_version'] == "2.0.0"
        assert v2_metrics['meta']['ticker'] == v1_metrics['ticker']
        
        # Should preserve raw values
        assert 'price' in v2_metrics
        assert 'audit_index' in v2_metrics
        
        # Should have display values
        price = v2_metrics['price']
        assert 'current' in price
        assert 'display' in price['current']
        assert '$' in price['current']['display']
    
    def test_build_enhanced_metrics_v2_returns_conversion(self):
        """Test returns conversion from v1 to v2."""
        v1_metrics = load_fixture('aapl_metrics_complete.json')
        
        v2_metrics = build_enhanced_metrics_v2(v1_metrics)
        
        returns_v2 = v2_metrics['price']['returns']
        returns_v1 = v1_metrics['price_metrics']['returns']
        
        # Should have both raw and display
        assert 'raw' in returns_v2
        assert 'display' in returns_v2
        
        # Raw values should match v1
        for period in returns_v1:
            if returns_v1[period] is not None:
                assert returns_v2['raw'][period] == returns_v1[period]
                
                # Display should be formatted percentage
                expected_display = f"{returns_v1[period] * 100:.1f}%"
                if returns_v1[period] < 0:
                    expected_display = f"-{abs(returns_v1[period] * 100):.1f}%"
                
                assert returns_v2['display'][period] == expected_display
    
    def test_build_enhanced_metrics_v2_volatility_conversion(self):
        """Test volatility conversion with classification."""
        v1_metrics = load_fixture('aapl_metrics_complete.json')
        
        v2_metrics = build_enhanced_metrics_v2(v1_metrics)
        
        volatility_v2 = v2_metrics['price']['volatility']
        volatility_v1 = v1_metrics['price_metrics']['volatility']
        
        # Should have enhanced fields
        assert 'raw' in volatility_v2
        assert 'display' in volatility_v2
        assert 'level' in volatility_v2
        assert 'window_display' in volatility_v2
        
        # Check classification
        vol_21d = volatility_v1.get('21D_annualized')
        if vol_21d is not None:
            assert volatility_v2['raw'] == vol_21d
            assert volatility_v2['display'] == f"{vol_21d * 100:.1f}%"
            
            # Check level classification
            if vol_21d < 0.20:
                assert volatility_v2['level'] == "low"
            elif vol_21d <= 0.35:
                assert volatility_v2['level'] == "moderate"
            else:
                assert volatility_v2['level'] == "high"
    
    def test_build_enhanced_metrics_v2_drawdown_conversion(self):
        """Test drawdown conversion with recovery status."""
        v1_metrics = load_fixture('aapl_metrics_complete.json')
        
        v2_metrics = build_enhanced_metrics_v2(v1_metrics)
        
        drawdown_v2 = v2_metrics['price']['drawdown']
        drawdown_v1 = v1_metrics['price_metrics']['drawdown']
        
        # Should have enhanced fields
        assert 'max_dd_raw' in drawdown_v2
        assert 'max_dd_display' in drawdown_v2
        assert 'recovery_status' in drawdown_v2
        assert 'recovered' in drawdown_v2
        
        # Check raw value preservation
        if drawdown_v1.get('max_drawdown_pct') is not None:
            assert drawdown_v2['max_dd_raw'] == drawdown_v1['max_drawdown_pct']
            
            # Check display formatting
            expected_display = f"{abs(drawdown_v1['max_drawdown_pct'] * 100):.1f}%"
            assert drawdown_v2['max_dd_display'] == f"-{expected_display}"
            
            # Check recovery status
            if drawdown_v1.get('recovery_date'):
                assert drawdown_v2['recovered'] is True
                assert 'fully recovered' in drawdown_v2['recovery_status']
            else:
                assert drawdown_v2['recovered'] is False
                assert 'unrecovered' in drawdown_v2['recovery_status']
    
    def test_build_enhanced_metrics_v2_concentration_conversion(self):
        """Test 13F concentration conversion with classification."""
        v1_metrics = load_fixture('aapl_metrics_complete.json')
        
        v2_metrics = build_enhanced_metrics_v2(v1_metrics)
        
        ownership_v2 = v2_metrics.get('ownership_13f')
        inst_v1 = v1_metrics.get('institutional_metrics')
        
        if inst_v1:
            assert ownership_v2 is not None
            
            concentration_v2 = ownership_v2['concentration']
            concentration_v1 = inst_v1['concentration']
            
            # Should have classification
            assert 'basis' in concentration_v2
            assert 'level' in concentration_v2
            
            # Should prefer CR5
            if concentration_v1.get('cr5') is not None:
                assert concentration_v2['basis'] == 'CR5'
                assert concentration_v2['cr5']['raw'] == concentration_v1['cr5']
                assert concentration_v2['cr5']['display'] == f"{concentration_v1['cr5'] * 100:.1f}%"
    
    def test_build_enhanced_metrics_v2_audit_index_population(self):
        """Test that audit index is properly populated."""
        v1_metrics = load_fixture('aapl_metrics_complete.json')
        
        v2_metrics = build_enhanced_metrics_v2(v1_metrics)
        
        audit_index = v2_metrics['audit_index']
        
        # Should have all required categories
        required_categories = [
            'percent_strings', 'currency_strings', 'dates',
            'labels', 'numbers', 'windows'
        ]
        
        for category in required_categories:
            assert category in audit_index
            assert isinstance(audit_index[category], list)
        
        # Should contain display values from metrics
        price = v2_metrics['price']
        
        # Returns display values should be in audit index
        for period, display_val in price['returns']['display'].items():
            if display_val != "Not available":
                assert display_val in audit_index['percent_strings']
        
        # Volatility display should be in audit index
        vol_display = price['volatility']['display']
        if vol_display != "Not available":
            assert vol_display in audit_index['percent_strings']
    
    def test_build_enhanced_metrics_v2_missing_data_handling(self):
        """Test handling of missing data in v1 metrics."""
        # Create minimal v1 metrics with missing sections
        minimal_v1 = {
            'ticker': 'TEST',
            'as_of_date': '2025-09-06',
            'data_period': {'trading_days': 10},
            'price_metrics': {
                'returns': {'1D': 0.01, '1M': None},  # Partial data
                'volatility': {'21D_annualized': None},  # Missing
                'drawdown': {'max_drawdown_pct': None},  # Missing
                'current_price': {'close': 100.0, 'date': '2025-09-05'}
            },
            'institutional_metrics': None,  # Missing
            'data_quality': {},
            'metadata': {'run_id': 1, 'data_sources': ['yfinance']}
        }
        
        v2_metrics = build_enhanced_metrics_v2(minimal_v1)
        
        # Should handle missing data gracefully
        assert v2_metrics['meta']['ticker'] == 'TEST'
        
        # Returns with partial data
        returns = v2_metrics['price']['returns']
        assert returns['display']['1D'] == "1.0%"  # Available
        assert returns['display']['1M'] == "Not available"  # Missing
        
        # Missing volatility
        volatility = v2_metrics['price']['volatility']
        assert volatility['display'] == "Not available"
        assert volatility['level'] == "unknown"
        
        # Missing institutional metrics
        assert v2_metrics.get('ownership_13f') is None
    
    def test_build_enhanced_metrics_v2_deterministic(self):
        """Test that v1→v2 conversion is deterministic."""
        v1_metrics = load_fixture('aapl_metrics_complete.json')
        
        # Convert twice
        v2_metrics_1 = build_enhanced_metrics_v2(v1_metrics)
        v2_metrics_2 = build_enhanced_metrics_v2(v1_metrics)
        
        # Remove timestamps (will be different)
        del v2_metrics_1['meta']['as_of_utc']
        del v2_metrics_2['meta']['as_of_utc']
        
        # Should be identical
        assert v2_metrics_1 == v2_metrics_2
