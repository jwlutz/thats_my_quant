"""
Tests for report rendering - MetricsJSON file to Markdown file.
Seeded file → assert exact content matches expected.
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import date

# Import renderer (will be created next)
from reports.render_report import (
    render_report,
    ReportRenderError,
    _find_metrics_file,
    _create_output_path
)


class TestRenderReport:
    """Tests for render_report function."""
    
    def test_render_report_success(self):
        """Test successful report rendering."""
        # Create test metrics file
        test_metrics = {
            'ticker': 'TEST',
            'as_of_date': '2025-09-06',
            'data_period': {'start_date': '2025-08-01', 'end_date': '2025-09-06', 'trading_days': 25},
            'price_metrics': {
                'returns': {'1D': 0.0234, '1W': 0.0456},
                'volatility': {'21D_annualized': 0.2845},
                'drawdown': {'max_drawdown_pct': -0.0856, 'peak_date': '2025-08-15', 'trough_date': '2025-08-20'},
                'current_price': {'close': 123.45, 'date': '2025-09-05'}
            },
            'institutional_metrics': None,
            'data_quality': {'price_coverage_pct': 96.0, 'missing_price_days': 1},
            'metadata': {'calculated_at': '2025-09-06T10:00:00', 'data_sources': ['yfinance']}
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            
            # Create metrics file
            metrics_file = workspace / 'TEST.json'
            with open(metrics_file, 'w') as f:
                json.dump(test_metrics, f)
            
            # Render report
            result = render_report(
                ticker='TEST',
                metrics_dir=workspace,
                output_dir=workspace / 'reports'
            )
            
            # Verify result
            assert result['status'] == 'completed'
            assert result['ticker'] == 'TEST'
            assert 'output_path' in result
            
            # Verify output file exists
            output_path = Path(result['output_path'])
            assert output_path.exists()
            
            # Verify content
            with open(output_path, 'r') as f:
                markdown = f.read()
            
            assert '# Stock Analysis Report: TEST' in markdown
            assert '$123.45' in markdown
            assert '2.34%' in markdown
            assert 'TEST' in markdown
    
    def test_render_report_no_metrics_file(self):
        """Test rendering when metrics file doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            
            result = render_report(
                ticker='NONEXISTENT',
                metrics_dir=workspace,
                output_dir=workspace / 'reports'
            )
            
            assert result['status'] == 'failed'
            assert 'No metrics file found' in result['error_message']
    
    def test_render_report_invalid_json(self):
        """Test rendering with invalid JSON file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            
            # Create invalid JSON file
            metrics_file = workspace / 'INVALID.json'
            with open(metrics_file, 'w') as f:
                f.write('{"invalid": json}')  # Invalid JSON
            
            result = render_report(
                ticker='INVALID',
                metrics_dir=workspace,
                output_dir=workspace / 'reports'
            )
            
            assert result['status'] == 'failed'
            assert 'Failed to load metrics' in result['error_message']
    
    def test_render_report_creates_output_directory(self):
        """Test that output directory is created if it doesn't exist."""
        test_metrics = {
            'ticker': 'TEST',
            'as_of_date': '2025-09-06',
            'data_period': {'trading_days': 1},
            'price_metrics': {'returns': {}, 'volatility': {}, 'current_price': {'close': 100.0, 'date': '2025-09-06'}},
            'institutional_metrics': None,
            'data_quality': {},
            'metadata': {'calculated_at': '2025-09-06T10:00:00', 'data_sources': []}
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            
            # Create metrics file
            metrics_file = workspace / 'TEST.json'
            with open(metrics_file, 'w') as f:
                json.dump(test_metrics, f)
            
            # Output to non-existent directory
            output_dir = workspace / 'deep' / 'nested' / 'reports'
            
            result = render_report(
                ticker='TEST',
                metrics_dir=workspace,
                output_dir=output_dir
            )
            
            assert result['status'] == 'completed'
            assert output_dir.exists()  # Directory was created
            
            output_path = Path(result['output_path'])
            assert output_path.exists()


class TestHelperFunctions:
    """Tests for helper functions."""
    
    def test_find_metrics_file(self):
        """Test finding metrics file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            
            # Create metrics file
            metrics_file = workspace / 'AAPL.json'
            metrics_file.write_text('{}')
            
            # Should find the file
            found = _find_metrics_file('AAPL', workspace)
            assert found == metrics_file
            
            # Should return None if not found
            not_found = _find_metrics_file('NONEXISTENT', workspace)
            assert not_found is None
    
    def test_create_output_path(self):
        """Test output path creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / 'reports'
            
            # Test with date
            path = _create_output_path('AAPL', output_dir, date(2025, 9, 6))
            
            assert 'AAPL' in str(path)
            assert '2025_09_06' in str(path)
            assert path.suffix == '.md'
            
            # Test without date (should use today)
            path_today = _create_output_path('MSFT', output_dir)
            assert 'MSFT' in str(path_today)
            assert path_today.suffix == '.md'
