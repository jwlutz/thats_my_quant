"""
LangChain chains for polish-only LLM narrative generation.
Executive summary and risk bullets with structured parsers.
"""

import re
import hashlib
import logging
from typing import Dict, Any, List, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.runnables import Runnable
from langchain_ollama import OllamaLLM

from reports.langchain_setup import ensure_langchain_ready
from reports.skeleton_builder import build_exec_summary_skeleton

# Set up logger
logger = logging.getLogger(__name__)


class ExecSummaryParser(BaseOutputParser[str]):
    """Parser for executive summary output with word count enforcement."""
    
    min_words: int = 120
    max_words: int = 180
    
    def parse(self, text: str) -> str:
        """Parse and validate executive summary output."""
        # Clean up the text
        cleaned = text.strip()
        
        # Remove ONLY outermost enclosing quotes (preserve internal quotes, hyphens, %, parentheses)
        if len(cleaned) >= 2:
            if cleaned.startswith('"') and cleaned.endswith('"'):
                cleaned = cleaned[1:-1].strip()
            elif cleaned.startswith("'") and cleaned.endswith("'"):
                cleaned = cleaned[1:-1].strip()
        
        # Count words
        words = cleaned.split()
        word_count = len(words)
        
        # Enforce length constraints
        if word_count < self.min_words:
            # Too short - this should trigger a retry
            raise ValueError(f"Executive summary too short: {word_count} words (minimum {self.min_words})")
        
        if word_count > self.max_words:
            # Too long - truncate at sentence boundary
            cleaned = self._truncate_at_sentence(cleaned, self.max_words)
        
        return cleaned
    
    def _truncate_at_sentence(self, text: str, max_words: int) -> str:
        """Truncate text at sentence boundary near max_words using regex."""
        import re
        
        words = text.split()
        if len(words) <= max_words:
            return text
        
        # Take approximately max_words
        truncated_words = words[:max_words]
        truncated_text = ' '.join(truncated_words)
        
        # Find last sentence boundary using regex (.?!)
        sentence_endings = list(re.finditer(r'[.?!]', truncated_text))
        if sentence_endings:
            last_sentence_end = sentence_endings[-1].end()
            return truncated_text[:last_sentence_end].strip()
        else:
            # No sentence boundary found, hard truncate with ellipsis
            return ' '.join(words[:max_words-1]) + '...'


class RiskBulletsParser(BaseOutputParser[List[str]]):
    """Parser for risk bullets output with count enforcement."""
    
    min_bullets: int = 3
    max_bullets: int = 5
    
    def parse(self, text: str) -> List[str]:
        """Parse and validate risk bullets output."""
        # Clean up the text
        cleaned = text.strip()
        
        # Extract bullets from text
        bullets = self._extract_bullets(cleaned)
        
        # Validate count
        if len(bullets) < self.min_bullets:
            raise ValueError(f"Too few risk bullets: {len(bullets)} (minimum {self.min_bullets})")
        
        if len(bullets) > self.max_bullets:
            # Truncate to max bullets
            bullets = bullets[:self.max_bullets]
        
        return bullets
    
    def _extract_bullets(self, text: str) -> List[str]:
        """Extract bullet points from text."""
        bullets = []
        
        # Split by common bullet patterns
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove bullet markers
            bullet_text = re.sub(r'^[-•*]\s*', '', line)
            bullet_text = re.sub(r'^\d+\.\s*', '', bullet_text)
            
            if bullet_text:
                bullets.append(bullet_text)
        
        # If no clear bullets found, try splitting by sentences
        if len(bullets) < 2:
            sentences = text.split('.')
            bullets = [s.strip() for s in sentences if s.strip()]
        
        return bullets


def create_exec_summary_chain(
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    min_words: int = 120,
    max_words: int = 180
) -> Runnable:
    """
    Create executive summary LangChain chain.
    
    Args:
        model_name: Ollama model name (defaults to env)
        base_url: Ollama base URL (defaults to env)
        min_words: Minimum word count
        max_words: Maximum word count
        
    Returns:
        Runnable chain for executive summary generation
    """
    # Ensure LangChain is ready
    ensure_langchain_ready()
    
    # Create LLM with deterministic parameters
    llm_options = {
        'temperature': 0.0,
        'top_p': 1.0, 
        'repeat_penalty': 1.0,
        'num_predict': 512  # Enough for 180 words + overhead
    }
    
    llm = OllamaLLM(
        model=model_name or "llama3.1:8b",
        base_url=base_url or "http://localhost:11434",
        **llm_options
    )
    
    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a neutral financial analyst. Your task is to polish the provided executive summary skeleton for readability while preserving ALL numbers, dates, and facts exactly as given.

CRITICAL RULES:
1. NEVER change, calculate, or invent any numbers or dates
2. Use ONLY the data provided in the skeleton
3. Polish for flow and readability while keeping all facts intact
4. Output MUST be {min_words}-{max_words} words
5. Write as a single paragraph
6. Use professional, neutral tone"""),
        ("human", """Polish this executive summary skeleton for readability. Keep all numbers and dates exactly as provided:

{skeleton}

Remember: {min_words}-{max_words} words, single paragraph, preserve all data exactly.""")
    ])
    
    # Create parser with custom limits
    parser = ExecSummaryParser()
    parser.min_words = min_words
    parser.max_words = max_words
    
    # Chain components together
    chain = prompt | llm | parser
    
    return chain


def create_risk_bullets_chain(
    model_name: Optional[str] = None,
    base_url: Optional[str] = None,
    min_bullets: int = 3,
    max_bullets: int = 5
) -> Runnable:
    """
    Create risk bullets LangChain chain.
    
    Args:
        model_name: Ollama model name (defaults to env)
        base_url: Ollama base URL (defaults to env)
        min_bullets: Minimum bullet count
        max_bullets: Maximum bullet count
        
    Returns:
        Runnable chain for risk bullets generation
    """
    # Ensure LangChain is ready
    ensure_langchain_ready()
    
    # Create LLM with deterministic parameters
    llm_options = {
        'temperature': 0.0,
        'top_p': 1.0, 
        'repeat_penalty': 1.0,
        'num_predict': 256  # Enough for 5 bullets
    }
    
    llm = OllamaLLM(
        model=model_name or "llama3.1:8b",
        base_url=base_url or "http://localhost:11434",
        **llm_options
    )
    
    # Create prompt template
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a neutral financial risk analyst. Generate {min_bullets}-{max_bullets} risk bullet points based on the provided metrics data.

CRITICAL RULES:
1. NEVER invent new numbers or dates not in the provided data
2. Focus on risks implied by the actual metrics shown
3. Each bullet should be a concise risk statement
4. Use only factual data from the provided metrics
5. Format as simple bullet points (one per line)
6. Professional, neutral tone"""),
        ("human", """Generate {min_bullets}-{max_bullets} risk bullet points based on this Enhanced MetricsJSON v2 data:

{metrics_json}

Focus on risks that can be inferred from the actual data provided. Do not invent new numbers.""")
    ])
    
    # Create parser with custom limits
    parser = RiskBulletsParser()
    parser.min_bullets = min_bullets
    parser.max_bullets = max_bullets
    
    # Chain components together
    chain = prompt | parser
    
    return chain


def generate_exec_summary(
    metrics_v2: Dict[str, Any],
    max_retries: int = 1,  # Max 1 retry, then fallback
    **chain_kwargs
) -> str:
    """
    Generate executive summary from Enhanced MetricsJSON v2.
    
    Args:
        metrics_v2: Enhanced MetricsJSON v2 dictionary
        max_retries: Maximum retry attempts
        **chain_kwargs: Additional arguments for chain creation
        
    Returns:
        Polished executive summary string
        
    Raises:
        Exception: If generation fails after retries
    """
    # Build skeleton first
    skeleton = build_exec_summary_skeleton(metrics_v2)
    
    # Create chain
    chain = create_exec_summary_chain(**chain_kwargs)
    
    # Log generation attempt
    model_name = chain_kwargs.get("model_name", "llama3.1:8b")
    prompt_hash = hashlib.md5(skeleton.encode()).hexdigest()[:8]
    logger.info(f"Generating exec summary: model={model_name}, prompt_hash={prompt_hash}, skeleton_words={len(skeleton.split())}")
    
    # Attempt generation with retries
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = chain.invoke({
                "skeleton": skeleton,
                "min_words": chain_kwargs.get("min_words", 120),
                "max_words": chain_kwargs.get("max_words", 180)
            })
            logger.info(f"Exec summary generated successfully: attempt={attempt+1}, output_words={len(result.split())}")
            return result
        except Exception as e:
            last_error = e
            logger.warning(f"Exec summary attempt {attempt+1} failed: {e}")
            if attempt < max_retries:
                continue
            break
    
    # If all retries failed, return skeleton as fallback
    logger.warning(f"Exec summary fallback to skeleton: final_error={last_error}")
    return skeleton


def generate_risk_bullets(
    metrics_v2: Dict[str, Any],
    max_retries: int = 1,  # Max 1 retry, then fallback
    **chain_kwargs
) -> List[str]:
    """
    Generate risk bullets from Enhanced MetricsJSON v2.
    
    Args:
        metrics_v2: Enhanced MetricsJSON v2 dictionary
        max_retries: Maximum retry attempts
        **chain_kwargs: Additional arguments for chain creation
        
    Returns:
        List of risk bullet strings
        
    Raises:
        Exception: If generation fails after retries
    """
    # Create chain
    chain = create_risk_bullets_chain(**chain_kwargs)
    
    # Convert metrics to JSON string for prompt
    import json
    metrics_json = json.dumps(metrics_v2, indent=2)
    
    # Log generation attempt
    model_name = chain_kwargs.get("model_name", "llama3.1:8b")
    prompt_hash = hashlib.md5(metrics_json.encode()).hexdigest()[:8]
    logger.info(f"Generating risk bullets: model={model_name}, prompt_hash={prompt_hash}")
    
    # Attempt generation with retries
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            result = chain.invoke({
                "metrics_json": metrics_json,
                "min_bullets": chain_kwargs.get("min_bullets", 3),
                "max_bullets": chain_kwargs.get("max_bullets", 5)
            })
            logger.info(f"Risk bullets generated successfully: attempt={attempt+1}, bullets_count={len(result)}")
            return result
        except Exception as e:
            last_error = e
            logger.warning(f"Risk bullets attempt {attempt+1} failed: {e}")
            if attempt < max_retries:
                continue
            break
    
    # If all retries failed, return fallback bullets
    fallback_bullets = [
        "Market volatility risk based on observed price movements",
        "Concentration risk in institutional ownership structure", 
        "Liquidity risk during market stress periods"
    ]
    logger.warning(f"Risk bullets fallback to default: final_error={last_error}")
    return fallback_bullets
