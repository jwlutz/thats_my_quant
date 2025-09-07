"""
Tests for Markdown template rendering.
Unit test: known MetricsJSON → golden .md file.
"""

import pytest
import json
from pathlib import Path

# Import template renderer (will be created next)
from reports.markdown_template import (
    render_metrics_report,
    TemplateError,
    format_percentage,
    format_currency,
    format_date_range
)


def load_fixture(filename):
    """Load fixture from tests/fixtures directory."""
    fixture_path = Path(__file__).parent.parent.parent / 'tests/fixtures' / filename
    with open(fixture_path, 'r') as f:
        return json.load(f)


class TestMarkdownTemplate:
    """Tests for Markdown template rendering."""
    
    def test_render_metrics_report_complete(self):
        """Test rendering complete metrics to Markdown."""
        metrics = load_fixture('expected_aapl_metrics.json')
        
        markdown = render_metrics_report(metrics)
        
        # Should be valid Markdown string
        assert isinstance(markdown, str)
        assert len(markdown) > 100  # Should be substantial
        
        # Should contain key sections
        assert '# Stock Analysis Report: AAPL' in markdown
        assert '## Price Metrics' in markdown
        assert '## Institutional Holdings' in markdown
        assert '## Data Quality' in markdown
        
        # Should contain key data points
        assert 'AAPL' in markdown
        assert '2025-08-07' in markdown  # as_of_date
        assert '$225.40' in markdown     # current price
        
        # Should format percentages correctly
        assert '%' in markdown
        
        # Should have table formatting
        assert '|' in markdown  # Table separators
        assert '---' in markdown  # Table headers
    
    def test_render_metrics_price_only(self):
        """Test rendering with price metrics only (no 13F data)."""
        metrics = {
            'ticker': 'TEST',
            'as_of_date': '2025-09-06',
            'data_period': {'start_date': '2025-08-01', 'end_date': '2025-09-06', 'trading_days': 25},
            'price_metrics': {
                'returns': {'1D': 0.0234, '1W': 0.0456, '1M': None},
                'volatility': {'21D_annualized': 0.2845, '63D_annualized': None},
                'drawdown': {'max_drawdown_pct': -0.0856, 'peak_date': '2025-08-15', 'trough_date': '2025-08-20', 'recovery_date': None},
                'current_price': {'close': 123.45, 'date': '2025-09-05'}
            },
            'institutional_metrics': None,
            'data_quality': {'price_coverage_pct': 96.0, 'missing_price_days': 1, 'latest_13f_quarter': None},
            'metadata': {'calculated_at': '2025-09-06T10:00:00', 'data_sources': ['yfinance']}
        }
        
        markdown = render_metrics_report(metrics)
        
        # Should handle missing 13F data gracefully
        assert 'No institutional holdings data available' in markdown
        assert 'TEST' in markdown
        assert '$123.45' in markdown
        
        # Should show available metrics
        assert '2.34%' in markdown  # 1D return
        assert '28.45%' in markdown  # Volatility
        
        # Should indicate missing metrics
        assert 'Not available' in markdown or 'N/A' in markdown
    
    def test_render_metrics_minimal_data(self):
        """Test rendering with minimal data."""
        metrics = {
            'ticker': 'MINIMAL',
            'as_of_date': '2025-09-06',
            'data_period': {'trading_days': 2},
            'price_metrics': {
                'returns': {'1D': 0.01, '1W': None, '1M': None},
                'volatility': {'21D_annualized': None},
                'drawdown': {'max_drawdown_pct': None},
                'current_price': {'close': 50.0, 'date': '2025-09-05'}
            },
            'institutional_metrics': None,
            'data_quality': {'price_coverage_pct': 100.0},
            'metadata': {'calculated_at': '2025-09-06T10:00:00', 'data_sources': ['yfinance']}
        }
        
        markdown = render_metrics_report(metrics)
        
        # Should handle minimal data gracefully
        assert 'MINIMAL' in markdown
        assert '$50.00' in markdown
        assert 'Limited data available' in markdown or 'Insufficient data' in markdown


class TestFormatHelpers:
    """Tests for formatting helper functions."""
    
    def test_format_percentage(self):
        """Test percentage formatting."""
        assert format_percentage(0.1234) == '12.34%'
        assert format_percentage(-0.0567) == '-5.67%'
        assert format_percentage(None) == 'N/A'
        assert format_percentage(0.0) == '0.00%'
    
    def test_format_currency(self):
        """Test currency formatting."""
        assert format_currency(1234567890) == '$1.23B'
        assert format_currency(1234567) == '$1.23M'
        assert format_currency(1234) == '$1,234'
        assert format_currency(None) == 'N/A'
        assert format_currency(0) == '$0'
    
    def test_format_date_range(self):
        """Test date range formatting."""
        result = format_date_range('2025-01-01', '2025-12-31', 252)
        assert '2025-01-01' in result
        assert '2025-12-31' in result
        assert '252' in result
        
        # Test with None values
        result = format_date_range(None, None, 0)
        assert 'Not available' in result or 'N/A' in result
    
    def test_format_percentage_with_direction(self):
        """Test percentage formatting with directional indicators."""
        # Positive return
        formatted = format_percentage(0.0534, show_direction=True)
        assert '📈' in formatted or '+' in formatted
        assert '5.34%' in formatted
        
        # Negative return
        formatted = format_percentage(-0.0234, show_direction=True)
        assert '%' in formatted and ('.' in formatted or '-' in formatted)
        assert '2.34%' in formatted
    
    def test_format_currency_scale_selection(self):
        """Test currency formatting scale selection."""
        # Billions
        assert 'B' in format_currency(5000000000)
        
        # Millions
        assert 'M' in format_currency(5000000)
        
        # Thousands
        assert ',' in format_currency(5000) and 'M' not in format_currency(5000)
        
        # Small amounts
        assert format_currency(50) == '$50'


class TestTemplateEdgeCases:
    """Tests for template edge cases."""
    
    def test_empty_metrics_error(self):
        """Test with empty metrics dictionary."""
        with pytest.raises(TemplateError, match="Empty or invalid metrics"):
            render_metrics_report({})
    
    def test_missing_required_fields(self):
        """Test with missing required fields."""
        incomplete_metrics = {
            'ticker': 'TEST'
            # Missing required fields
        }
        
        with pytest.raises(TemplateError, match="Missing required field"):
            render_metrics_report(incomplete_metrics)
    
    def test_malformed_data_structures(self):
        """Test with malformed data structures."""
        malformed_metrics = {
            'ticker': 'TEST',
            'as_of_date': '2025-09-06',
            'price_metrics': 'not_a_dict',  # Should be dict
            'data_period': {'trading_days': 10},
            'institutional_metrics': None,
            'data_quality': {},
            'metadata': {}
        }
        
        with pytest.raises(TemplateError, match="Invalid data structure"):
            render_metrics_report(malformed_metrics)
