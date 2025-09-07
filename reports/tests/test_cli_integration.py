"""
Integration tests for CLI with LangChain integration.
"""

import pytest
from unittest.mock import patch, MagicMock
import tempfile
import json
from pathlib import Path

# Import CLI functions
import sys
sys.path.append(str(Path(__file__).parent.parent.parent))
from cli import generate_report


class TestCLIIntegration:
    """Test CLI integration with LangChain."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.test_v1_metrics = {
            "metadata": {
                "ticker": "TEST",
                "run_id": 12345,
                "analysis_date": "2025-01-15",
                "data_sources": ["yfinance", "sec_edgar"]
            },
            "price_metrics": {
                "current_price": 100.0,
                "returns": {
                    "1D": -0.003,
                    "1M": 0.089,
                    "1Y": 0.213
                },
                "volatility": {
                    "21D_annualized": 0.285
                },
                "drawdown": {
                    "max_drawdown": -0.185,
                    "peak_date": "2025-07-15",
                    "trough_date": "2025-08-12",
                    "recovery_date": "2025-08-28"
                }
            },
            "ownership_13f": {
                "total_value": 125000000000.0,
                "total_holders": 145,
                "as_of": "2024-09-30",
                "concentration": {
                    "cr5": 0.123,
                    "hhi": 0.012
                },
                "top_holders": [
                    {"rank": 1, "filer": "VANGUARD GROUP INC", "value": 5700000000.0}
                ]
            }
        }
    
    @patch('cli.write_both_atomic')
    @patch('cli.update_latest_pointer')
    @patch('cli.update_cross_ticker_index')
    @patch('cli.create_report_paths')
    @patch('cli.build_enhanced_metrics_v2')
    def test_cli_llm_disabled_default(self, mock_v2_builder, mock_paths, mock_index, mock_pointer, mock_write):
        """Test CLI with LLM disabled (default behavior)."""
        # Mock file system
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics_file = Path(temp_dir) / "TEST.json"
            with open(metrics_file, 'w') as f:
                json.dump(self.test_v1_metrics, f)
            
            # Mock dependencies
            mock_v2_builder.return_value = {
                "meta": {"ticker": "TEST", "company": "Test Inc", "run_id": 12345},
                "audit_index": {"percent_strings": ["28.5%"], "dates": ["July 15, 2025"]},
                "price": {"current": {"display": "$100.00", "date_display": "January 15, 2025"}},
                "ownership_13f": None
            }
            
            mock_paths.return_value = {
                "report_path": Path(temp_dir) / "report.md",
                "metrics_path": Path(temp_dir) / "metrics.json",
                "latest_path": Path(temp_dir) / "latest.md",
                "ticker_dir": Path(temp_dir)
            }
            
            mock_write.return_value = {"status": "completed", "report_bytes": 1000}
            mock_pointer.return_value = {"status": "completed", "strategy": "copy"}
            mock_index.return_value = {"status": "completed", "entries_count": 1}
            
            # Patch file existence check
            with patch('cli.Path.exists', return_value=True), \
                 patch('cli.open', mock=MagicMock()) as mock_open, \
                 patch('builtins.open', mock=MagicMock()) as mock_builtin_open:
                
                # Configure file reading
                mock_builtin_open.return_value.__enter__.return_value.read.return_value = json.dumps(self.test_v1_metrics)
                
                # Test CLI with LLM disabled (default)
                generate_report("TEST", llm_enabled=False)
                
                # Verify no LLM calls were made
                mock_write.assert_called_once()
                report_content = mock_write.call_args[1]['report_content']
                
                # Should contain skeleton but no risk analysis section
                assert "## Executive Summary" in report_content
                assert "## Risk Analysis" not in report_content
    
    @patch('cli.generate_exec_summary')
    @patch('cli.generate_risk_bullets')
    @patch('cli.write_both_atomic')
    @patch('cli.update_latest_pointer')
    @patch('cli.update_cross_ticker_index')
    @patch('cli.create_report_paths')
    @patch('cli.build_enhanced_metrics_v2')
    def test_cli_llm_enabled(self, mock_v2_builder, mock_paths, mock_index, mock_pointer, mock_write, mock_risk_bullets, mock_exec_summary):
        """Test CLI with LLM enabled."""
        # Mock file system
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics_file = Path(temp_dir) / "TEST.json"
            with open(metrics_file, 'w') as f:
                json.dump(self.test_v1_metrics, f)
            
            # Mock dependencies
            mock_v2_builder.return_value = {
                "meta": {"ticker": "TEST", "company": "Test Inc", "run_id": 12345},
                "audit_index": {"percent_strings": ["28.5%"], "dates": ["July 15, 2025"]},
                "price": {"current": {"display": "$100.00", "date_display": "January 15, 2025"}},
                "ownership_13f": None
            }
            
            mock_paths.return_value = {
                "report_path": Path(temp_dir) / "report.md",
                "metrics_path": Path(temp_dir) / "metrics.json",
                "latest_path": Path(temp_dir) / "latest.md",
                "ticker_dir": Path(temp_dir)
            }
            
            mock_write.return_value = {"status": "completed", "report_bytes": 1000}
            mock_pointer.return_value = {"status": "completed", "strategy": "copy"}
            mock_index.return_value = {"status": "completed", "entries_count": 1}
            
            # Mock LLM responses
            mock_exec_summary.return_value = "This is a polished executive summary with 28.5% return from July 15, 2025."
            mock_risk_bullets.return_value = [
                "Market volatility risk at 28.5% level",
                "Drawdown risk from July 15, 2025 event",
                "Institutional concentration risk"
            ]
            
            # Patch file existence check
            with patch('cli.Path.exists', return_value=True), \
                 patch('cli.open', mock=MagicMock()) as mock_open, \
                 patch('builtins.open', mock=MagicMock()) as mock_builtin_open:
                
                # Configure file reading
                mock_builtin_open.return_value.__enter__.return_value.read.return_value = json.dumps(self.test_v1_metrics)
                
                # Test CLI with LLM enabled
                generate_report("TEST", llm_enabled=True)
                
                # Verify LLM calls were made
                mock_exec_summary.assert_called_once()
                mock_risk_bullets.assert_called_once()
                
                # Verify report content includes both sections
                mock_write.assert_called_once()
                report_content = mock_write.call_args[1]['report_content']
                
                assert "## Executive Summary" in report_content
                assert "## Risk Analysis" in report_content
                assert "This is a polished executive summary" in report_content
                assert "Market volatility risk at 28.5% level" in report_content
    
    @patch('cli.generate_exec_summary')
    @patch('cli.generate_risk_bullets')
    @patch('cli.build_exec_summary_skeleton')
    @patch('cli.write_both_atomic')
    @patch('cli.update_latest_pointer')
    @patch('cli.update_cross_ticker_index')
    @patch('cli.create_report_paths')
    @patch('cli.build_enhanced_metrics_v2')
    def test_cli_llm_fallback_on_error(self, mock_v2_builder, mock_paths, mock_index, mock_pointer, mock_write, mock_skeleton, mock_risk_bullets, mock_exec_summary):
        """Test CLI fallback behavior when LLM fails."""
        # Mock file system
        with tempfile.TemporaryDirectory() as temp_dir:
            metrics_file = Path(temp_dir) / "TEST.json"
            with open(metrics_file, 'w') as f:
                json.dump(self.test_v1_metrics, f)
            
            # Mock dependencies
            mock_v2_builder.return_value = {
                "meta": {"ticker": "TEST", "company": "Test Inc", "run_id": 12345},
                "audit_index": {"percent_strings": ["28.5%"], "dates": ["July 15, 2025"]},
                "price": {"current": {"display": "$100.00", "date_display": "January 15, 2025"}},
                "ownership_13f": None
            }
            
            mock_paths.return_value = {
                "report_path": Path(temp_dir) / "report.md",
                "metrics_path": Path(temp_dir) / "metrics.json",
                "latest_path": Path(temp_dir) / "latest.md",
                "ticker_dir": Path(temp_dir)
            }
            
            mock_write.return_value = {"status": "completed", "report_bytes": 1000}
            mock_pointer.return_value = {"status": "completed", "strategy": "copy"}
            mock_index.return_value = {"status": "completed", "entries_count": 1}
            
            # Mock LLM failures
            mock_exec_summary.side_effect = Exception("LLM service unavailable")
            mock_risk_bullets.side_effect = Exception("LLM service unavailable")
            mock_skeleton.return_value = "Safe skeleton summary without LLM."
            
            # Patch file existence check
            with patch('cli.Path.exists', return_value=True), \
                 patch('cli.open', mock=MagicMock()) as mock_open, \
                 patch('builtins.open', mock=MagicMock()) as mock_builtin_open:
                
                # Configure file reading
                mock_builtin_open.return_value.__enter__.return_value.read.return_value = json.dumps(self.test_v1_metrics)
                
                # Test CLI with LLM enabled but failing
                generate_report("TEST", llm_enabled=True)
                
                # Verify fallback was used
                mock_exec_summary.assert_called_once()
                mock_skeleton.assert_called_once()
                
                # Verify report uses fallback content
                mock_write.assert_called_once()
                report_content = mock_write.call_args[1]['report_content']
                
                assert "Safe skeleton summary without LLM" in report_content
                assert "## Risk Analysis" in report_content  # Should still have fallback bullets
