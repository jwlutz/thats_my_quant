"""
LLM polisher for executive summaries.
Uses Ollama to polish skeleton for readability without changing data.
"""

from typing import Dict, Any
import re

# Import Ollama client
from reports.ollama_client import ollama_request, OllamaError


class LLMPolisherError(Exception):
    """Raised when LLM polishing fails."""
    pass


# Prompt contracts
SYSTEM_PROMPT = """You are a neutral equity research analyst. Use ONLY the provided data. Do not invent numbers or dates. No recommendations or price targets. If a field is missing, write "Not available." Keep to one paragraph (120-180 words)."""

DEVELOPER_PROMPT = """You will receive (A) a DRAFT paragraph that already contains all numbers and dates pulled from METRICS, and (B) the raw METRICS JSON. Edit the DRAFT for clarity and flow without altering any numbers or dates and without adding new ones."""

USER_PROMPT = """Improve the DRAFT summary for readability. Keep one paragraph (120-180 words). Do not change any numeric values or dates; do not add any new figures."""


def polish_executive_summary(
    skeleton: str,
    metrics_v2: Dict[str, Any],
    model: str = None,
    timeout: int = 60
) -> Dict[str, Any]:
    """
    Polish executive summary skeleton using LLM.
    
    Args:
        skeleton: Pre-filled skeleton with all data
        metrics_v2: Enhanced MetricsJSON v2 for context
        model: Ollama model to use (defaults to env)
        timeout: Request timeout in seconds
        
    Returns:
        Dictionary with polishing results
    """
    try:
        # Prepare full prompt
        full_prompt = f"""DRAFT paragraph to improve:
{skeleton}

METRICS JSON for reference:
{_extract_relevant_metrics(metrics_v2)}

{USER_PROMPT}"""
        
        # Make LLM request
        polished_text = ollama_request(
            prompt=full_prompt,
            system_prompt=SYSTEM_PROMPT,
            model=model,
            timeout=timeout
        )
        
        # Clean up response
        polished_text = _clean_llm_response(polished_text)
        
        # Validate word count
        word_count = len(polished_text.split())
        if word_count > 180:
            polished_text = _truncate_to_word_limit(polished_text, 180)
        elif word_count < 120:
            # If too short, fall back to skeleton
            polished_text = skeleton
        
        return {
            'status': 'completed',
            'polished_text': polished_text,
            'original_skeleton': skeleton,
            'word_count': len(polished_text.split()),
            'model_used': model
        }
        
    except OllamaError as e:
        return {
            'status': 'failed',
            'error': str(e),
            'fallback_text': skeleton,
            'word_count': len(skeleton.split()),
            'model_used': model
        }
    except Exception as e:
        return {
            'status': 'failed', 
            'error': f"Unexpected polishing error: {e}",
            'fallback_text': skeleton,
            'word_count': len(skeleton.split())
        }


def _extract_relevant_metrics(metrics_v2: Dict[str, Any]) -> str:
    """Extract relevant metrics for LLM context (condensed)."""
    # Only include essential data to avoid prompt bloat
    relevant = {
        'ticker': metrics_v2['meta']['ticker'],
        'current_price': metrics_v2['price']['current']['display'],
        'returns_display': metrics_v2['price']['returns']['display'],
        'volatility': {
            'level': metrics_v2['price']['volatility']['level'],
            'display': metrics_v2['price']['volatility']['display']
        },
        'drawdown': {
            'display': metrics_v2['price']['drawdown']['max_dd_display'],
            'recovery_status': metrics_v2['price']['drawdown']['recovery_status']
        }
    }
    
    # Add concentration if available
    ownership = metrics_v2.get('ownership_13f')
    if ownership:
        relevant['concentration'] = {
            'level': ownership['concentration']['level'],
            'basis': ownership['concentration']['basis']
        }
    
    import json
    return json.dumps(relevant, indent=2)


def _clean_llm_response(response: str) -> str:
    """Clean LLM response of unwanted formatting."""
    # Remove markdown formatting
    cleaned = re.sub(r'\*\*(.*?)\*\*', r'\1', response)  # Remove bold
    cleaned = re.sub(r'\*(.*?)\*', r'\1', cleaned)       # Remove italic
    
    # Remove bullet points if any
    cleaned = re.sub(r'^\s*[-•*]\s+', '', cleaned, flags=re.MULTILINE)
    
    # Remove extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.strip()
    
    # Ensure it's one paragraph
    sentences = cleaned.split('.')
    if len(sentences) > 1:
        # Join sentences with proper spacing
        cleaned = '. '.join(s.strip() for s in sentences if s.strip())
        if not cleaned.endswith('.'):
            cleaned += '.'
    
    return cleaned


def _truncate_to_word_limit(text: str, max_words: int) -> str:
    """Truncate text to word limit at sentence boundary."""
    words = text.split()
    if len(words) <= max_words:
        return text
    
    # Take first max_words
    truncated_words = words[:max_words]
    truncated_text = ' '.join(truncated_words)
    
    # Find last sentence boundary
    last_period = truncated_text.rfind('.')
    if last_period > 0 and last_period > len(truncated_text) * 0.8:
        # Good sentence boundary found
        return truncated_text[:last_period + 1]
    else:
        # No good boundary, add ellipsis
        return truncated_text + '...'


def validate_polished_output(
    polished_text: str,
    original_skeleton: str,
    metrics_v2: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate that polished output meets requirements.
    
    Args:
        polished_text: LLM polished text
        original_skeleton: Original skeleton
        metrics_v2: Enhanced metrics for audit
        
    Returns:
        Dictionary with validation results
    """
    validation = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'word_count': len(polished_text.split()),
        'length_valid': True,
        'structure_valid': True
    }
    
    # Word count validation
    word_count = validation['word_count']
    if word_count < 120:
        validation['errors'].append(f"Too short: {word_count} words (min 120)")
        validation['valid'] = False
        validation['length_valid'] = False
    elif word_count > 180:
        validation['errors'].append(f"Too long: {word_count} words (max 180)")
        validation['valid'] = False
        validation['length_valid'] = False
    
    # Structure validation (should be one paragraph)
    paragraph_count = polished_text.count('\n\n') + 1
    if paragraph_count > 1:
        validation['warnings'].append(f"Multiple paragraphs detected: {paragraph_count}")
        validation['structure_valid'] = False
    
    # Check for prohibited language
    prohibited_words = ['will', 'should', 'expect', 'likely', 'probably', 'target', 'recommend']
    found_prohibited = []
    text_lower = polished_text.lower()
    
    for word in prohibited_words:
        if word in text_lower:
            found_prohibited.append(word)
    
    if found_prohibited:
        validation['errors'].append(f"Prohibited words found: {found_prohibited}")
        validation['valid'] = False
    
    return validation
