"""
Integration tests for audit system with LangChain chains.
"""

import pytest
from unittest.mock import patch, MagicMock

from reports.langchain_chains import generate_exec_summary, generate_risk_bullets


class TestAuditIntegration:
    """Test audit integration with LangChain chains."""
    
    @patch('reports.langchain_chains.create_exec_summary_chain')
    @patch('reports.langchain_chains.build_exec_summary_skeleton')
    def test_exec_summary_audit_pass(self, mock_skeleton, mock_chain):
        """Test exec summary with audit passing."""
        # Mock skeleton
        mock_skeleton.return_value = "Safe skeleton with 28.5% return from July 15, 2025."
        
        # Mock chain that returns text with allowed numbers/dates
        mock_chain_instance = MagicMock()
        mock_chain_instance.invoke.return_value = "Polished text with 28.5% return from July 15, 2025."
        mock_chain.return_value = mock_chain_instance
        
        # Metrics with matching audit_index
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%"],
                "dates": ["July 15, 2025"]
            }
        }
        
        result = generate_exec_summary(metrics_v2)
        
        # Should return the polished text (audit passed)
        assert result == "Polished text with 28.5% return from July 15, 2025."
        mock_chain_instance.invoke.assert_called_once()
    
    @patch('reports.langchain_chains.create_exec_summary_chain')
    @patch('reports.langchain_chains.build_exec_summary_skeleton')
    def test_exec_summary_audit_fail_fallback(self, mock_skeleton, mock_chain):
        """Test exec summary with audit failing and fallback to skeleton."""
        # Mock skeleton
        skeleton_text = "Safe skeleton with 28.5% return from July 15, 2025."
        mock_skeleton.return_value = skeleton_text
        
        # Mock chain that returns text with unauthorized numbers/dates
        mock_chain_instance = MagicMock()
        mock_chain_instance.invoke.return_value = "Polished text with 99.9% return from January 1, 2025."  # Unauthorized
        mock_chain.return_value = mock_chain_instance
        
        # Metrics with limited audit_index
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%"],
                "dates": ["July 15, 2025"]
            }
        }
        
        result = generate_exec_summary(metrics_v2)
        
        # Should return the skeleton (audit failed)
        assert result == skeleton_text
        mock_chain_instance.invoke.assert_called_once()
    
    @patch('reports.langchain_chains.create_risk_bullets_chain')
    def test_risk_bullets_audit_pass(self, mock_chain):
        """Test risk bullets with audit passing."""
        # Mock chain that returns bullets with allowed numbers/dates
        mock_chain_instance = MagicMock()
        mock_chain_instance.invoke.return_value = [
            "Volatility risk at 28.5% level",
            "Drawdown risk from July 15, 2025 event",
            "Market concentration risk"
        ]
        mock_chain.return_value = mock_chain_instance
        
        # Metrics with matching audit_index
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%"],
                "dates": ["July 15, 2025"]
            }
        }
        
        result = generate_risk_bullets(metrics_v2)
        
        # Should return the original bullets (audit passed)
        assert len(result) == 3
        assert "Volatility risk at 28.5% level" in result
        assert "Drawdown risk from July 15, 2025 event" in result
        assert "Market concentration risk" in result
    
    @patch('reports.langchain_chains.create_risk_bullets_chain')
    def test_risk_bullets_audit_fail_fallback(self, mock_chain):
        """Test risk bullets with audit failing and fallback."""
        # Mock chain that returns bullets with unauthorized numbers/dates
        mock_chain_instance = MagicMock()
        mock_chain_instance.invoke.return_value = [
            "Volatility risk at 99.9% level",  # Unauthorized percentage
            "Drawdown risk from January 1, 2025 event",  # Unauthorized date
            "Market concentration risk"  # Safe
        ]
        mock_chain.return_value = mock_chain_instance
        
        # Metrics with limited audit_index
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%"],
                "dates": ["July 15, 2025"]
            }
        }
        
        result = generate_risk_bullets(metrics_v2)
        
        # Should return fallback for unauthorized bullets, original for safe ones
        assert len(result) == 3
        assert result[0] == "Risk factor 1 based on observed market conditions"  # Fallback
        assert result[1] == "Risk factor 2 based on observed market conditions"  # Fallback
        assert result[2] == "Market concentration risk"  # Original (safe)
    
    @patch('reports.langchain_chains.create_exec_summary_chain')
    @patch('reports.langchain_chains.build_exec_summary_skeleton')
    def test_exec_summary_audit_tolerance(self, mock_skeleton, mock_chain):
        """Test exec summary audit with tolerance handling."""
        # Mock skeleton
        mock_skeleton.return_value = "Safe skeleton with 28.5% return."
        
        # Mock chain that returns text with slightly different formatting
        mock_chain_instance = MagicMock()
        mock_chain_instance.invoke.return_value = "Polished text with 28.50% return."  # 28.50% vs 28.5%
        mock_chain.return_value = mock_chain_instance
        
        # Metrics with audit_index
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["28.5%"],
                "dates": []
            }
        }
        
        result = generate_exec_summary(metrics_v2)
        
        # Should return the polished text (within tolerance)
        assert result == "Polished text with 28.50% return."
        mock_chain_instance.invoke.assert_called_once()
    
    def test_audit_with_empty_audit_index(self):
        """Test audit behavior with empty audit_index."""
        metrics_v2 = {"audit_index": {}}
        
        # Any text with numbers/dates should fail audit
        with patch('reports.langchain_chains.create_exec_summary_chain') as mock_chain, \
             patch('reports.langchain_chains.build_exec_summary_skeleton') as mock_skeleton:
            
            skeleton_text = "Safe skeleton without numbers or dates."
            mock_skeleton.return_value = skeleton_text
            
            mock_chain_instance = MagicMock()
            mock_chain_instance.invoke.return_value = "Text with 28.5% return."
            mock_chain.return_value = mock_chain_instance
            
            result = generate_exec_summary(metrics_v2)
            
            # Should fallback to skeleton (no allowed numbers)
            assert result == skeleton_text
    
    def test_audit_with_missing_audit_index(self):
        """Test audit behavior with missing audit_index."""
        metrics_v2 = {}  # No audit_index at all
        
        # Any text with numbers/dates should fail audit
        with patch('reports.langchain_chains.create_exec_summary_chain') as mock_chain, \
             patch('reports.langchain_chains.build_exec_summary_skeleton') as mock_skeleton:
            
            skeleton_text = "Safe skeleton without numbers or dates."
            mock_skeleton.return_value = skeleton_text
            
            mock_chain_instance = MagicMock()
            mock_chain_instance.invoke.return_value = "Text with 28.5% return."
            mock_chain.return_value = mock_chain_instance
            
            result = generate_exec_summary(metrics_v2)
            
            # Should fallback to skeleton (no allowed numbers)
            assert result == skeleton_text


class TestAuditEdgeCases:
    """Test audit edge cases with real integration."""
    
    def test_negative_zero_percentage_tolerance(self):
        """Test that -0.0% matches 0.0% within tolerance."""
        metrics_v2 = {
            "audit_index": {
                "percent_strings": ["0.0%"],  # Should match -0.0%
                "dates": []
            }
        }
        
        with patch('reports.langchain_chains.create_exec_summary_chain') as mock_chain, \
             patch('reports.langchain_chains.build_exec_summary_skeleton') as mock_skeleton:
            
            mock_skeleton.return_value = "Safe skeleton."
            
            mock_chain_instance = MagicMock()
            mock_chain_instance.invoke.return_value = "No change at -0.0% today."
            mock_chain.return_value = mock_chain_instance
            
            result = generate_exec_summary(metrics_v2)
            
            # Should pass audit (-0.0% normalizes to 0.0)
            assert result == "No change at -0.0% today."
    
    def test_date_leading_zeros_normalization(self):
        """Test that dates with leading zeros are normalized correctly."""
        metrics_v2 = {
            "audit_index": {
                "percent_strings": [],
                "dates": ["August 5, 2025"]  # No leading zero
            }
        }
        
        with patch('reports.langchain_chains.create_exec_summary_chain') as mock_chain, \
             patch('reports.langchain_chains.build_exec_summary_skeleton') as mock_skeleton:
            
            mock_skeleton.return_value = "Safe skeleton."
            
            mock_chain_instance = MagicMock()
            mock_chain_instance.invoke.return_value = "Event on August 05, 2025."  # With leading zero
            mock_chain.return_value = mock_chain_instance
            
            result = generate_exec_summary(metrics_v2)
            
            # Should pass audit (both normalize to 2025-08-05)
            assert result == "Event on August 05, 2025."
