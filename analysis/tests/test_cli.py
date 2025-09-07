"""
Tests for CLI entry points - subprocess calls in temp workspace.
Tests actual command execution with seeded DB.
"""

import pytest
import subprocess
import sqlite3
import json
import tempfile
import sys
from datetime import date, datetime
from pathlib import Path

# Test utilities
from storage.loaders import init_database, upsert_prices, upsert_13f


@pytest.fixture
def temp_workspace():
    """Create temporary workspace with database and test data."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        
        # Create database with test data
        db_path = workspace / 'research.db'
        conn = sqlite3.connect(str(db_path))
        init_database(conn)
        
        # Insert test price data for AAPL
        price_data = [
            {
                'ticker': 'AAPL', 'date': date(2025, 8, 1),
                'open': 220.50, 'high': 222.30, 'low': 219.80, 'close': 221.75, 'adj_close': 221.50,
                'volume': 45000000, 'source': 'yfinance', 'as_of': date(2025, 8, 1),
                'ingested_at': datetime(2025, 8, 2, 9, 0, 0)
            },
            {
                'ticker': 'AAPL', 'date': date(2025, 8, 4),
                'open': 221.80, 'high': 223.45, 'low': 221.20, 'close': 222.90, 'adj_close': 222.65,
                'volume': 38000000, 'source': 'yfinance', 'as_of': date(2025, 8, 4),
                'ingested_at': datetime(2025, 8, 5, 9, 0, 0)
            },
            {
                'ticker': 'AAPL', 'date': date(2025, 8, 5),
                'open': 222.95, 'high': 224.10, 'low': 222.40, 'close': 223.55, 'adj_close': 223.30,
                'volume': 42000000, 'source': 'yfinance', 'as_of': date(2025, 8, 5),
                'ingested_at': datetime(2025, 8, 6, 9, 0, 0)
            }
        ]
        upsert_prices(conn, price_data)
        
        # Insert test 13F data
        holdings_data = [
            {
                'cik': '0001067983', 'filer': 'BERKSHIRE HATHAWAY INC',
                'ticker': 'AAPL', 'name': 'APPLE INC', 'cusip': '037833100',
                'value_usd': 50000000000.0, 'shares': 250000000.0,
                'as_of': date(2024, 9, 30), 'source': 'sec_edgar',
                'ingested_at': datetime(2025, 1, 15, 10, 0, 0)
            }
        ]
        upsert_13f(conn, holdings_data)
        
        conn.close()
        
        yield workspace


class TestAnalyzeTickerCLI:
    """Tests for analyze_ticker CLI command."""
    
    def test_analyze_ticker_cli_success(self, temp_workspace):
        """Test successful CLI execution."""
        db_path = temp_workspace / 'research.db'
        output_path = temp_workspace / 'AAPL_metrics.json'
        
        # Get the project root to find the CLI script
        project_root = Path(__file__).parent.parent.parent
        cli_script = project_root / 'analysis' / 'analyze_ticker.py'
        
        # Run CLI command
        result = subprocess.run([
            sys.executable, str(cli_script),
            'AAPL',
            '--db-path', str(db_path),
            '--output', str(output_path),
            '--as-of', '2025-08-05'
        ], capture_output=True, text=True, cwd=str(project_root))
        
        # Should succeed
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        
        # Output file should exist
        assert output_path.exists()
        
        # Should contain valid MetricsJSON
        with open(output_path, 'r') as f:
            metrics = json.load(f)
        
        assert metrics['ticker'] == 'AAPL'
        assert 'price_metrics' in metrics
        assert 'institutional_metrics' in metrics
    
    def test_analyze_ticker_cli_no_data(self, temp_workspace):
        """Test CLI with ticker that has no data."""
        db_path = temp_workspace / 'research.db'
        output_path = temp_workspace / 'INVALID_metrics.json'
        
        project_root = Path(__file__).parent.parent.parent
        cli_script = project_root / 'analysis' / 'analyze_ticker.py'
        
        result = subprocess.run([
            sys.executable, str(cli_script),
            'INVALID',  # No data for this ticker
            '--db-path', str(db_path),
            '--output', str(output_path)
        ], capture_output=True, text=True, cwd=str(project_root))
        
        # Should fail gracefully
        assert result.returncode != 0
        assert 'No price data' in result.stderr
        
        # Output file should not exist
        assert not output_path.exists()
    
    def test_analyze_ticker_cli_default_paths(self, temp_workspace):
        """Test CLI with default paths."""
        # Copy database to expected default location
        default_db = temp_workspace / 'data' / 'research.db'
        default_db.parent.mkdir(exist_ok=True)
        
        source_db = temp_workspace / 'research.db'
        import shutil
        shutil.copy2(source_db, default_db)
        
        project_root = Path(__file__).parent.parent.parent
        cli_script = project_root / 'analysis' / 'analyze_ticker.py'
        
        result = subprocess.run([
            sys.executable, str(cli_script),
            'AAPL'  # Just ticker, use defaults
        ], capture_output=True, text=True, cwd=str(temp_workspace))
        
        # Should succeed with defaults
        assert result.returncode == 0
        
        # Default output should exist
        default_output = temp_workspace / 'data' / 'processed' / 'metrics' / 'AAPL.json'
        assert default_output.exists()


class TestShowMetricsCLI:
    """Tests for show_metrics CLI command."""
    
    def test_show_metrics_cli_success(self, temp_workspace):
        """Test show_metrics CLI with existing metrics file."""
        # Create a metrics file first
        metrics_dir = temp_workspace / 'data' / 'processed' / 'metrics'
        metrics_dir.mkdir(parents=True)
        
        metrics_file = metrics_dir / 'AAPL.json'
        test_metrics = {
            'ticker': 'AAPL',
            'as_of_date': '2025-08-05',
            'price_metrics': {
                'returns': {'1D': 0.0234, '1W': 0.0456, '1M': 0.0891},
                'volatility': {'21D_annualized': 0.2845},
                'current_price': {'close': 223.55, 'date': '2025-08-05'}
            },
            'institutional_metrics': {
                'total_13f_value_usd': 80000000000.0,
                'concentration': {'cr1': 0.625, 'cr5': 1.0, 'hhi': 0.4525}
            }
        }
        
        with open(metrics_file, 'w') as f:
            json.dump(test_metrics, f)
        
        project_root = Path(__file__).parent.parent.parent
        cli_script = project_root / 'analysis' / 'show_metrics.py'
        
        result = subprocess.run([
            sys.executable, str(cli_script),
            'AAPL',
            '--metrics-dir', str(metrics_dir)
        ], capture_output=True, text=True, cwd=str(project_root))
        
        # Should succeed and show metrics
        assert result.returncode == 0
        
        # Output should contain key metrics
        output = result.stdout
        assert 'AAPL' in output
        assert '2.34%' in output  # 1D return
        assert '28.45%' in output  # Volatility
        assert '$223.55' in output  # Current price
    
    def test_show_metrics_cli_no_file(self, temp_workspace):
        """Test show_metrics CLI with no metrics file."""
        metrics_dir = temp_workspace / 'data' / 'processed' / 'metrics'
        
        project_root = Path(__file__).parent.parent.parent
        cli_script = project_root / 'analysis' / 'show_metrics.py'
        
        result = subprocess.run([
            sys.executable, str(cli_script),
            'NONEXISTENT',
            '--metrics-dir', str(metrics_dir)
        ], capture_output=True, text=True, cwd=str(project_root))
        
        # Should fail gracefully
        assert result.returncode != 0
        assert 'No metrics found' in result.stderr
