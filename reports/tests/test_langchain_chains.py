"""
Tests for LangChain chains and parsers.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from reports.langchain_chains import (
    ExecSummaryParser,
    RiskBulletsParser,
    create_exec_summary_chain,
    create_risk_bullets_chain,
    generate_exec_summary,
    generate_risk_bullets
)


class TestExecSummaryParser:
    """Test executive summary parser."""
    
    def test_valid_summary(self):
        """Test parsing valid summary within word limits."""
        class TestParser(ExecSummaryParser):
            min_words: int = 10
            max_words: int = 20
        parser = TestParser()
        
        text = "This is a valid executive summary with exactly fourteen words in the paragraph format."
        result = parser.parse(text)
        
        assert result == text
        assert len(result.split()) == 14
    
    def test_remove_quotes(self):
        """Test removal of quotes around response."""
        class TestParser(ExecSummaryParser):
            min_words: int = 5
            max_words: int = 20
        parser = TestParser()
        
        # Double quotes
        text = '"This is a quoted response from the model."'
        result = parser.parse(text)
        assert result == "This is a quoted response from the model."
        
        # Single quotes
        text = "'This is a single quoted response.'"
        result = parser.parse(text)
        assert result == "This is a single quoted response."
    
    def test_too_short_raises_error(self):
        """Test that too short summary raises ValueError."""
        class TestParser(ExecSummaryParser):
            min_words: int = 20
            max_words: int = 30
        parser = TestParser()
        
        text = "Too short."
        with pytest.raises(ValueError) as exc_info:
            parser.parse(text)
        
        assert "too short" in str(exc_info.value).lower()
        assert "2 words" in str(exc_info.value)
    
    def test_too_long_truncated(self):
        """Test that too long summary is truncated."""
        class TestParser(ExecSummaryParser):
            min_words: int = 5
            max_words: int = 10
        parser = TestParser()
        
        text = "This is a very long executive summary that exceeds the maximum word limit and should be truncated at sentence boundary."
        result = parser.parse(text)
        
        words = result.split()
        assert len(words) <= 10
        # Should end with period or ellipsis
        assert result.endswith('.') or result.endswith('...')
    
    def test_truncate_at_sentence_boundary(self):
        """Test truncation at sentence boundary."""
        class TestParser(ExecSummaryParser):
            min_words: int = 5
            max_words: int = 15
        parser = TestParser()
        
        text = "First sentence has eight words right here. Second sentence would definitely make it exceed the fifteen word limit."
        result = parser.parse(text)
        
        # Should truncate at sentence boundary (first sentence is 7 words, within limit)
        assert result == "First sentence has eight words right here."
        assert len(result.split()) == 7
    
    def test_truncate_without_sentence_boundary(self):
        """Test truncation when no sentence boundary available."""
        class TestParser(ExecSummaryParser):
            min_words: int = 5
            max_words: int = 10
        parser = TestParser()
        
        text = "This is one very long sentence without any periods that would normally provide sentence boundaries"
        result = parser.parse(text)
        
        words = result.split()
        assert len(words) <= 10
        assert result.endswith('...')


class TestRiskBulletsParser:
    """Test risk bullets parser."""
    
    def test_valid_bullets(self):
        """Test parsing valid bullet points."""
        class TestParser(RiskBulletsParser):
            min_bullets: int = 3
            max_bullets: int = 5
        parser = TestParser()
        
        text = """- Market volatility risk
• Liquidity risk during stress
* Concentration risk in holdings"""
        
        result = parser.parse(text)
        
        assert len(result) == 3
        assert result[0] == "Market volatility risk"
        assert result[1] == "Liquidity risk during stress"
        assert result[2] == "Concentration risk in holdings"
    
    def test_numbered_bullets(self):
        """Test parsing numbered bullet points."""
        class TestParser(RiskBulletsParser):
            min_bullets: int = 2
            max_bullets: int = 4
        parser = TestParser()
        
        text = """1. First risk factor
2. Second risk factor
3. Third risk factor"""
        
        result = parser.parse(text)
        
        assert len(result) == 3
        assert result[0] == "First risk factor"
        assert result[1] == "Second risk factor"
        assert result[2] == "Third risk factor"
    
    def test_sentence_fallback(self):
        """Test fallback to sentence splitting."""
        class TestParser(RiskBulletsParser):
            min_bullets: int = 2
            max_bullets: int = 4
        parser = TestParser()
        
        text = "Market risk is high. Liquidity risk exists. Concentration risk present."
        result = parser.parse(text)
        
        assert len(result) == 3
        assert "Market risk is high" in result[0]
        assert "Liquidity risk exists" in result[1]
        assert "Concentration risk present" in result[2]
    
    def test_too_few_bullets_raises_error(self):
        """Test that too few bullets raises ValueError."""
        class TestParser(RiskBulletsParser):
            min_bullets: int = 5
            max_bullets: int = 7
        parser = TestParser()
        
        text = "- Only one bullet\n- And another"
        with pytest.raises(ValueError) as exc_info:
            parser.parse(text)
        
        assert "too few" in str(exc_info.value).lower()
        assert "2" in str(exc_info.value)
    
    def test_too_many_bullets_truncated(self):
        """Test that too many bullets are truncated."""
        class TestParser(RiskBulletsParser):
            min_bullets: int = 2
            max_bullets: int = 3
        parser = TestParser()
        
        text = """- First bullet
- Second bullet  
- Third bullet
- Fourth bullet
- Fifth bullet"""
        
        result = parser.parse(text)
        
        assert len(result) == 3
        assert result[0] == "First bullet"
        assert result[1] == "Second bullet"
        assert result[2] == "Third bullet"


class TestCreateExecSummaryChain:
    """Test executive summary chain creation."""
    
    @patch('reports.langchain_chains.ensure_langchain_ready')
    @patch('reports.langchain_chains.OllamaLLM')
    def test_create_chain_success(self, mock_llm, mock_ensure):
        """Test successful chain creation."""
        mock_ensure.return_value = None
        mock_llm.return_value = MagicMock()

        chain = create_exec_summary_chain(
            model_name="test-model",
            base_url="http://test:11434",
            min_words=100,
            max_words=150
        )

        assert chain is not None
        mock_ensure.assert_called_once()
        mock_llm.assert_called_once_with(
            model="test-model",
            base_url="http://test:11434",
            temperature=0.0,
            top_p=1.0,
            repeat_penalty=1.0,
            num_predict=512
        )
    
    @patch('reports.langchain_chains.ensure_langchain_ready')
    def test_create_chain_setup_failure(self, mock_ensure):
        """Test chain creation with setup failure."""
        mock_ensure.side_effect = Exception("Setup failed")
        
        with pytest.raises(Exception) as exc_info:
            create_exec_summary_chain()
        
        assert "Setup failed" in str(exc_info.value)


class TestCreateRiskBulletsChain:
    """Test risk bullets chain creation."""
    
    @patch('reports.langchain_chains.ensure_langchain_ready')
    @patch('reports.langchain_chains.OllamaLLM')
    def test_create_chain_success(self, mock_llm, mock_ensure):
        """Test successful chain creation."""
        mock_ensure.return_value = None
        mock_llm.return_value = MagicMock()

        chain = create_risk_bullets_chain(
            model_name="test-model",
            base_url="http://test:11434",
            min_bullets=4,
            max_bullets=6
        )

        assert chain is not None
        mock_ensure.assert_called_once()
        mock_llm.assert_called_once_with(
            model="test-model",
            base_url="http://test:11434",
            temperature=0.0,
            top_p=1.0,
            repeat_penalty=1.0,
            num_predict=256
        )


class TestGenerateExecSummary:
    """Test executive summary generation."""
    
    @patch('reports.langchain_chains.create_exec_summary_chain')
    @patch('reports.langchain_chains.build_exec_summary_skeleton')
    def test_successful_generation(self, mock_skeleton, mock_chain):
        """Test successful executive summary generation."""
        # Mock skeleton
        mock_skeleton.return_value = "Test skeleton with enough words to meet minimum requirements for testing purposes."
        
        # Mock chain
        mock_chain_instance = MagicMock()
        mock_chain_instance.invoke.return_value = "Polished executive summary with exactly the right number of words for testing."
        mock_chain.return_value = mock_chain_instance
        
        metrics_v2 = {"meta": {"ticker": "TEST"}}
        result = generate_exec_summary(metrics_v2)
        
        assert result == "Polished executive summary with exactly the right number of words for testing."
        mock_skeleton.assert_called_once_with(metrics_v2)
        mock_chain.assert_called_once()
        mock_chain_instance.invoke.assert_called_once()
    
    @patch('reports.langchain_chains.create_exec_summary_chain')
    @patch('reports.langchain_chains.build_exec_summary_skeleton')
    def test_generation_with_retries(self, mock_skeleton, mock_chain):
        """Test executive summary generation with retries."""
        # Mock skeleton
        skeleton_text = "Test skeleton fallback text with sufficient words for minimum requirements."
        mock_skeleton.return_value = skeleton_text
        
        # Mock chain that fails twice then succeeds
        mock_chain_instance = MagicMock()
        mock_chain_instance.invoke.side_effect = [
            Exception("First failure"),
            Exception("Second failure"),
            "Success on third try"
        ]
        mock_chain.return_value = mock_chain_instance
        
        metrics_v2 = {"meta": {"ticker": "TEST"}}
        result = generate_exec_summary(metrics_v2, max_retries=2)
        
        assert result == "Success on third try"
        assert mock_chain_instance.invoke.call_count == 3
    
    @patch('reports.langchain_chains.create_exec_summary_chain')
    @patch('reports.langchain_chains.build_exec_summary_skeleton')
    def test_generation_fallback_to_skeleton(self, mock_skeleton, mock_chain):
        """Test fallback to skeleton when all retries fail."""
        # Mock skeleton
        skeleton_text = "Test skeleton fallback text with sufficient words for minimum requirements."
        mock_skeleton.return_value = skeleton_text
        
        # Mock chain that always fails
        mock_chain_instance = MagicMock()
        mock_chain_instance.invoke.side_effect = Exception("Always fails")
        mock_chain.return_value = mock_chain_instance
        
        metrics_v2 = {"meta": {"ticker": "TEST"}}
        result = generate_exec_summary(metrics_v2, max_retries=1)
        
        # Should return skeleton as fallback
        assert result == skeleton_text
        assert mock_chain_instance.invoke.call_count == 2  # max_retries + 1


class TestGenerateRiskBullets:
    """Test risk bullets generation."""
    
    @patch('reports.langchain_chains.create_risk_bullets_chain')
    def test_successful_generation(self, mock_chain):
        """Test successful risk bullets generation."""
        # Mock chain
        mock_chain_instance = MagicMock()
        mock_chain_instance.invoke.return_value = [
            "Market volatility risk",
            "Liquidity risk during stress",
            "Concentration risk in holdings"
        ]
        mock_chain.return_value = mock_chain_instance
        
        metrics_v2 = {"meta": {"ticker": "TEST"}}
        result = generate_risk_bullets(metrics_v2)
        
        assert len(result) == 3
        assert result[0] == "Market volatility risk"
        mock_chain.assert_called_once()
        mock_chain_instance.invoke.assert_called_once()
    
    @patch('reports.langchain_chains.create_risk_bullets_chain')
    def test_generation_with_retries(self, mock_chain):
        """Test risk bullets generation with retries."""
        # Mock chain that fails then succeeds
        mock_chain_instance = MagicMock()
        mock_chain_instance.invoke.side_effect = [
            Exception("First failure"),
            ["Success bullet 1", "Success bullet 2", "Success bullet 3"]
        ]
        mock_chain.return_value = mock_chain_instance
        
        metrics_v2 = {"meta": {"ticker": "TEST"}}
        result = generate_risk_bullets(metrics_v2, max_retries=1)
        
        assert len(result) == 3
        assert result[0] == "Success bullet 1"
        assert mock_chain_instance.invoke.call_count == 2
    
    @patch('reports.langchain_chains.create_risk_bullets_chain')
    def test_generation_fallback_to_default(self, mock_chain):
        """Test fallback to default bullets when all retries fail."""
        # Mock chain that always fails
        mock_chain_instance = MagicMock()
        mock_chain_instance.invoke.side_effect = Exception("Always fails")
        mock_chain.return_value = mock_chain_instance
        
        metrics_v2 = {"meta": {"ticker": "TEST"}}
        result = generate_risk_bullets(metrics_v2, max_retries=1)
        
        # Should return fallback bullets
        assert len(result) == 3
        assert "Market volatility risk" in result[0]
        assert "Concentration risk" in result[1]
        assert "Liquidity risk" in result[2]
        assert mock_chain_instance.invoke.call_count == 2  # max_retries + 1
