"""
Tests for Enhanced MetricsJSON v2 schema validation.
Schema/shape tests only - no calculations.
"""

import pytest
import json
from pathlib import Path

# Import v2 schema functions (will be created next)
from reports.metrics_v2_schema import (
    validate_v2_schema,
    V2SchemaError,
    SCHEMA_VERSION_V2
)


def load_fixture(filename):
    """Load JSON fixture from golden directory."""
    fixture_path = Path(__file__).parent.parent.parent / 'tests/fixtures/golden' / filename
    with open(fixture_path, 'r') as f:
        return json.load(f)


class TestV2Schema:
    """Tests for v2 schema validation."""
    
    def test_v2_schema_version(self):
        """Test that v2 schema version is defined."""
        assert SCHEMA_VERSION_V2 == "2.0.0"
    
    def test_validate_v2_schema_complete(self):
        """Test validation with complete v2 MetricsJSON."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        
        # Should not raise
        validation = validate_v2_schema(v2_metrics)
        
        assert validation['valid'] is True
        assert validation['schema_version'] == "2.0.0"
        assert validation['has_meta'] is True
        assert validation['has_price'] is True
        assert validation['has_audit_index'] is True
    
    def test_validate_v2_meta_section(self):
        """Test meta section validation."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        meta = v2_metrics['meta']
        
        # Required meta fields
        required_meta_fields = [
            'ticker', 'company', 'currency', 'as_of_local', 'as_of_utc',
            'timezone', 'run_id', 'sources', 'schema_version'
        ]
        
        for field in required_meta_fields:
            assert field in meta, f"Missing meta field: {field}"
        
        # Validate types
        assert isinstance(meta['ticker'], str)
        assert isinstance(meta['run_id'], int)
        assert isinstance(meta['sources'], list)
        assert meta['schema_version'] == "2.0.0"
    
    def test_validate_v2_price_section(self):
        """Test price section validation."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        price = v2_metrics['price']
        
        # Required price sections
        required_sections = ['current', 'returns', 'volatility', 'drawdown']
        for section in required_sections:
            assert section in price, f"Missing price section: {section}"
        
        # Validate current price structure
        current = price['current']
        assert 'value' in current and 'display' in current
        assert isinstance(current['value'], (int, float))
        assert isinstance(current['display'], str)
        assert '$' in current['display']
        
        # Validate returns structure
        returns = price['returns']
        assert 'raw' in returns and 'display' in returns
        assert isinstance(returns['raw'], dict)
        assert isinstance(returns['display'], dict)
        assert set(returns['raw'].keys()) == set(returns['display'].keys())
        
        # Validate volatility structure
        volatility = price['volatility']
        required_vol_fields = ['raw', 'display', 'level', 'window_display']
        for field in required_vol_fields:
            assert field in volatility
        assert volatility['level'] in ['low', 'moderate', 'high']
    
    def test_validate_v2_ownership_section(self):
        """Test ownership_13f section validation."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        ownership = v2_metrics.get('ownership_13f')
        
        if ownership:  # Optional section
            # Required fields when present
            required_fields = ['as_of', 'as_of_display', 'concentration']
            for field in required_fields:
                assert field in ownership
            
            # Validate concentration structure
            concentration = ownership['concentration']
            assert 'basis' in concentration
            assert 'level' in concentration
            assert concentration['basis'] in ['CR5', 'HHI']
            assert concentration['level'] in ['low', 'moderate', 'high']
            
            # Should have either CR5 or HHI data
            has_cr5 = 'cr5' in concentration
            has_hhi = 'hhi' in concentration
            assert has_cr5 or has_hhi, "Must have either CR5 or HHI data"
    
    def test_validate_v2_audit_index(self):
        """Test audit index validation."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        audit_index = v2_metrics['audit_index']
        
        # Required audit categories
        required_categories = [
            'percent_strings', 'currency_strings', 'dates',
            'labels', 'numbers', 'windows'
        ]
        
        for category in required_categories:
            assert category in audit_index
            assert isinstance(audit_index[category], list)
        
        # Validate content types
        for pct_str in audit_index['percent_strings']:
            assert isinstance(pct_str, str)
            assert '%' in pct_str
        
        for curr_str in audit_index['currency_strings']:
            assert isinstance(curr_str, str)
            assert '$' in curr_str
        
        for date_str in audit_index['dates']:
            assert isinstance(date_str, str)
            assert '2025' in date_str or '2024' in date_str  # Should have years
    
    def test_validate_v2_raw_display_consistency(self):
        """Test that raw and display values are consistent."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        
        # Check returns consistency
        returns = v2_metrics['price']['returns']
        for period in returns['raw']:
            raw_val = returns['raw'][period]
            display_val = returns['display'][period]
            
            if raw_val is not None:
                # Display should be formatted percentage
                expected_pct = f"{raw_val * 100:.1f}%"
                # Handle negative values
                if raw_val < 0:
                    assert display_val.startswith('-')
                assert display_val.replace('-', '') == expected_pct.replace('-', '')
        
        # Check volatility consistency
        volatility = v2_metrics['price']['volatility']
        vol_raw = volatility['raw']
        vol_display = volatility['display']
        expected_vol_display = f"{vol_raw * 100:.1f}%"
        assert vol_display == expected_vol_display
    
    def test_validate_v2_classification_consistency(self):
        """Test that classifications match thresholds."""
        v2_metrics = load_fixture('aapl_metrics_v2.json')
        
        # Test volatility classification
        volatility = v2_metrics['price']['volatility']
        vol_raw = volatility['raw']
        vol_level = volatility['level']
        
        if vol_raw < 0.20:
            expected_level = "low"
        elif vol_raw <= 0.35:
            expected_level = "moderate"
        else:
            expected_level = "high"
        
        assert vol_level == expected_level
        
        # Test concentration classification
        ownership = v2_metrics.get('ownership_13f')
        if ownership:
            concentration = ownership['concentration']
            basis = concentration['basis']
            level = concentration['level']
            
            if basis == 'CR5' and 'cr5' in concentration:
                cr5_raw = concentration['cr5']['raw']
                if cr5_raw < 0.25:
                    expected_level = "low"
                elif cr5_raw <= 0.40:
                    expected_level = "moderate"
                else:
                    expected_level = "high"
                assert level == expected_level


class TestV2SchemaValidation:
    """Tests for schema validation function."""
    
    def test_missing_required_sections(self):
        """Test validation with missing required sections."""
        incomplete_v2 = {
            "meta": {
                "ticker": "TEST",
                "schema_version": "2.0.0"
            }
            # Missing price, audit_index
        }
        
        with pytest.raises(V2SchemaError, match="Missing required section"):
            validate_v2_schema(incomplete_v2)
    
    def test_invalid_schema_version(self):
        """Test validation with wrong schema version."""
        invalid_v2 = {
            "meta": {
                "ticker": "TEST",
                "schema_version": "1.0.0"  # Wrong version
            },
            "price": {},
            "audit_index": {}
        }
        
        with pytest.raises(V2SchemaError, match="Invalid schema version"):
            validate_v2_schema(invalid_v2)
    
    def test_malformed_audit_index(self):
        """Test validation with malformed audit index."""
        malformed_v2 = {
            "meta": {"ticker": "TEST", "schema_version": "2.0.0"},
            "price": {"current": {"value": 100.0, "display": "$100.00"}},
            "audit_index": "not_a_dict"  # Should be dict
        }
        
        with pytest.raises(V2SchemaError, match="audit_index must be dict"):
            validate_v2_schema(malformed_v2)
