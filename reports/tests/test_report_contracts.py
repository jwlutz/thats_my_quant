"""
Tests for report contracts and schema validation.
Schema/shape tests: render stub templates = golden.
"""

import pytest
import json
from pathlib import Path

# Import contracts (will be created next)
from reports.report_contracts import (
    validate_report_structure,
    validate_metrics_json_for_reports,
    ReportContractError,
    REQUIRED_REPORT_SECTIONS,
    LLM_SECTION_SPECS
)


def load_fixture(filename):
    """Load fixture from tests/fixtures/golden directory."""
    fixture_path = Path(__file__).parent.parent.parent / 'tests/fixtures/golden' / filename
    
    if filename.endswith('.json'):
        with open(fixture_path, 'r') as f:
            return json.load(f)
    elif filename.endswith('.md'):
        with open(fixture_path, 'r') as f:
            return f.read()
    else:
        raise ValueError(f"Unknown fixture format: {filename}")


class TestReportContracts:
    """Tests for report structure contracts."""
    
    def test_required_report_sections(self):
        """Test that required sections are defined correctly."""
        expected_sections = [
            'title_block',
            'executive_summary', 
            'price_snapshot',
            'ownership_snapshot',
            'risks_watchlist',
            'appendix'
        ]
        
        assert REQUIRED_REPORT_SECTIONS == expected_sections
    
    def test_llm_section_specs(self):
        """Test LLM section specifications."""
        # Should have specs for LLM-generated sections
        assert 'executive_summary' in LLM_SECTION_SPECS
        assert 'risks_watchlist' in LLM_SECTION_SPECS
        
        # Each spec should have required fields
        for section_name, spec in LLM_SECTION_SPECS.items():
            assert 'word_count_min' in spec
            assert 'word_count_max' in spec
            assert 'format' in spec
            assert 'constraints' in spec
    
    def test_validate_metrics_json_complete(self):
        """Test validation with complete MetricsJSON."""
        metrics = load_fixture('aapl_metrics_complete.json')
        
        # Should not raise
        validate_metrics_json_for_reports(metrics)
    
    def test_validate_metrics_json_missing_sections(self):
        """Test validation with missing sections."""
        incomplete_metrics = {
            'ticker': 'TEST',
            'as_of_date': '2025-09-06',
            # Missing required sections
        }
        
        with pytest.raises(ReportContractError, match="Missing required section"):
            validate_metrics_json_for_reports(incomplete_metrics)
    
    def test_validate_report_structure(self):
        """Test report structure validation."""
        report_stub = load_fixture('aapl_report_stub.md')
        
        # Should validate structure
        structure = validate_report_structure(report_stub)
        
        # Should find all required sections
        assert structure['title_block']['found'] is True
        assert structure['price_snapshot']['found'] is True
        assert structure['ownership_snapshot']['found'] is True
        assert structure['appendix']['found'] is True
        
        # LLM sections should be marked as placeholders
        assert '[LLM narrative will be inserted here' in report_stub
    
    def test_validate_report_structure_missing_sections(self):
        """Test report validation with missing sections."""
        incomplete_report = """
        # Stock Research Report: TEST
        
        ## Price Snapshot
        Some content here.
        
        # Missing other sections
        """
        
        structure = validate_report_structure(incomplete_report)
        
        # Should detect missing sections
        missing_sections = [
            section for section, info in structure.items() 
            if not info['found'] and section in REQUIRED_REPORT_SECTIONS
        ]
        
        assert len(missing_sections) > 0
    
    def test_metrics_json_schema_compatibility(self):
        """Test that our MetricsJSON matches report requirements."""
        metrics = load_fixture('aapl_metrics_complete.json')
        
        # Should have all data needed for report sections
        
        # Title block data
        assert 'ticker' in metrics
        assert 'as_of_date' in metrics
        assert 'data_period' in metrics
        
        # Price snapshot data
        price_metrics = metrics['price_metrics']
        assert 'returns' in price_metrics
        assert 'volatility' in price_metrics
        assert 'drawdown' in price_metrics
        assert 'current_price' in price_metrics
        
        # Ownership snapshot data (can be None)
        inst_metrics = metrics.get('institutional_metrics')
        if inst_metrics:
            assert 'concentration' in inst_metrics
            assert 'top_holders' in inst_metrics
        
        # Appendix data
        assert 'data_quality' in metrics
        assert 'metadata' in metrics
    
    def test_report_section_ordering(self):
        """Test that report sections appear in correct order."""
        report_stub = load_fixture('aapl_report_stub.md')
        
        # Find section positions
        title_pos = report_stub.find('# Stock Research Report:')
        exec_pos = report_stub.find('## Executive Summary')
        price_pos = report_stub.find('## Price Snapshot')
        owner_pos = report_stub.find('## Ownership Snapshot')
        risks_pos = report_stub.find('## Risks & Watchlist')
        appendix_pos = report_stub.find('## Appendix')
        
        # Should be in order
        positions = [title_pos, exec_pos, price_pos, owner_pos, risks_pos, appendix_pos]
        assert positions == sorted(positions), "Sections not in correct order"
        assert all(pos >= 0 for pos in positions), "Some sections not found"
