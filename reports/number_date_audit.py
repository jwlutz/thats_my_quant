"""
Number and date audit for LLM output validation.
Ensures no new numbers/dates are introduced beyond audit_index.
"""

import re
import logging
from typing import Dict, Any, List, Set, Tuple
from dateutil import parser as date_parser
from datetime import datetime

# Set up logger
logger = logging.getLogger(__name__)


class AuditError(Exception):
    """Raised when audit validation fails."""
    pass


def extract_percentages(text: str) -> List[str]:
    r"""
    Extract percentage strings from text using deterministic regex.
    
    Pattern: [-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s?%
    
    Args:
        text: Input text to scan
        
    Returns:
        List of percentage strings found
    """
    pattern = r'[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s?%'
    return re.findall(pattern, text)


def extract_dates(text: str) -> List[str]:
    r"""
    Extract date strings from text using deterministic regex.
    
    Pattern: (January|February|...|December)\s+\d{1,2},\s+\d{4}
    
    Args:
        text: Input text to scan
        
    Returns:
        List of date strings found in Month D, YYYY format
    """
    months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    month_pattern = '|'.join(months)
    pattern = rf'(?:{month_pattern})\s+\d{{1,2}},\s+\d{{4}}'
    return re.findall(pattern, text, re.IGNORECASE)


def normalize_percentage(percent_str: str) -> float:
    """
    Normalize percentage string to float.
    
    Args:
        percent_str: Percentage string (e.g., "28.5%", "-18.50%", "1,234.5%")
        
    Returns:
        Float value (e.g., 0.285, -0.185, 12.345)
    """
    # Strip % and whitespace
    cleaned = percent_str.replace('%', '').strip()
    
    # Remove thousands separators
    cleaned = cleaned.replace(',', '')
    
    # Parse to float and convert to decimal (divide by 100)
    return float(cleaned) / 100.0


def normalize_date(date_str: str) -> str:
    """
    Normalize date string to YYYY-MM-DD format.
    
    Args:
        date_str: Date string in "Month D, YYYY" format
        
    Returns:
        Date string in YYYY-MM-DD format
    """
    try:
        # Parse the date string
        parsed_date = date_parser.parse(date_str)
        # Return in ISO format (YYYY-MM-DD)
        return parsed_date.strftime('%Y-%m-%d')
    except Exception as e:
        logger.warning(f"Failed to parse date '{date_str}': {e}")
        return date_str  # Return original if parsing fails


def build_audit_sets(metrics_v2: Dict[str, Any]) -> Tuple[Set[float], Set[str]]:
    """
    Build audit sets from Enhanced MetricsJSON v2.
    
    Args:
        metrics_v2: Enhanced MetricsJSON v2 dictionary
        
    Returns:
        Tuple of (numeric_percents_set, dates_iso_set)
    """
    audit_index = metrics_v2.get('audit_index', {})
    
    # Build numeric percentages set
    numeric_percents = set()
    percent_strings = audit_index.get('percent_strings', [])
    for percent_str in percent_strings:
        try:
            normalized = normalize_percentage(percent_str)
            numeric_percents.add(normalized)
        except Exception as e:
            logger.warning(f"Failed to normalize percentage '{percent_str}': {e}")
    
    # Build ISO dates set
    dates_iso = set()
    dates = audit_index.get('dates', [])
    for date_str in dates:
        try:
            normalized = normalize_date(date_str)
            dates_iso.add(normalized)
        except Exception as e:
            logger.warning(f"Failed to normalize date '{date_str}': {e}")
    
    return numeric_percents, dates_iso


def audit_text(
    text: str, 
    metrics_v2: Dict[str, Any], 
    tolerance: float = 0.0005
) -> Dict[str, Any]:
    """
    Audit text for unauthorized numbers and dates.
    
    Args:
        text: Text to audit
        metrics_v2: Enhanced MetricsJSON v2 dictionary
        tolerance: Tolerance for percentage comparison (±0.05 percentage points)
        
    Returns:
        Dictionary with audit results
    """
    # Extract tokens from text
    found_percentages = extract_percentages(text)
    found_dates = extract_dates(text)
    
    # Build allowed sets from audit_index
    allowed_percents, allowed_dates = build_audit_sets(metrics_v2)
    
    # Track violations
    violations = {
        'unauthorized_percentages': [],
        'unauthorized_dates': [],
        'total_violations': 0
    }
    
    # Check percentages
    for percent_str in found_percentages:
        try:
            normalized = normalize_percentage(percent_str)
            
            # Check if within tolerance of any allowed percentage
            is_allowed = False
            for allowed_percent in allowed_percents:
                if abs(normalized - allowed_percent) <= tolerance:
                    is_allowed = True
                    break
            
            if not is_allowed:
                violations['unauthorized_percentages'].append({
                    'text': percent_str,
                    'normalized': normalized,
                    'closest_allowed': min(allowed_percents, key=lambda x: abs(x - normalized)) if allowed_percents else None
                })
        except Exception as e:
            logger.warning(f"Failed to check percentage '{percent_str}': {e}")
            violations['unauthorized_percentages'].append({
                'text': percent_str,
                'error': str(e)
            })
    
    # Check dates
    for date_str in found_dates:
        try:
            normalized = normalize_date(date_str)
            
            if normalized not in allowed_dates:
                violations['unauthorized_dates'].append({
                    'text': date_str,
                    'normalized': normalized
                })
        except Exception as e:
            logger.warning(f"Failed to check date '{date_str}': {e}")
            violations['unauthorized_dates'].append({
                'text': date_str,
                'error': str(e)
            })
    
    # Calculate total violations
    violations['total_violations'] = (
        len(violations['unauthorized_percentages']) + 
        len(violations['unauthorized_dates'])
    )
    
    # Build result
    result = {
        'passed': violations['total_violations'] == 0,
        'found_percentages': found_percentages,
        'found_dates': found_dates,
        'violations': violations,
        'allowed_percents_count': len(allowed_percents),
        'allowed_dates_count': len(allowed_dates)
    }
    
    return result


def audit_with_fallback(
    text: str,
    skeleton: str,
    metrics_v2: Dict[str, Any],
    max_retries: int = 1,
    tolerance: float = 0.0005
) -> Tuple[str, bool]:
    """
    Audit text with fallback to skeleton on failure.
    
    Args:
        text: Text to audit (from LLM)
        skeleton: Fallback skeleton text
        metrics_v2: Enhanced MetricsJSON v2 dictionary
        max_retries: Number of retries before fallback (not used - for signature compatibility)
        tolerance: Tolerance for percentage comparison
        
    Returns:
        Tuple of (final_text, used_fallback)
    """
    # Perform audit
    audit_result = audit_text(text, metrics_v2, tolerance)
    
    if audit_result['passed']:
        logger.info(f"Audit passed: found {len(audit_result['found_percentages'])} percentages, {len(audit_result['found_dates'])} dates")
        return text, False
    else:
        # Log violations and fall back to skeleton
        violations = audit_result['violations']
        logger.warning(f"Audit failed with {violations['total_violations']} violations:")
        
        for violation in violations['unauthorized_percentages']:
            logger.warning(f"  Unauthorized percentage: {violation}")
        
        for violation in violations['unauthorized_dates']:
            logger.warning(f"  Unauthorized date: {violation}")
        
        logger.warning("Falling back to skeleton")
        return skeleton, True


def create_enhanced_audit_index(metrics_v2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create enhanced audit_index with numeric_percents and dates_iso.
    
    Args:
        metrics_v2: Enhanced MetricsJSON v2 dictionary
        
    Returns:
        Enhanced audit_index with additional numeric formats
    """
    audit_index = metrics_v2.get('audit_index', {}).copy()
    
    # Add numeric_percents
    numeric_percents = []
    percent_strings = audit_index.get('percent_strings', [])
    for percent_str in percent_strings:
        try:
            normalized = normalize_percentage(percent_str)
            numeric_percents.append(normalized)
        except Exception as e:
            logger.warning(f"Failed to normalize percentage '{percent_str}' for audit_index: {e}")
    
    # Add dates_iso
    dates_iso = []
    dates = audit_index.get('dates', [])
    for date_str in dates:
        try:
            normalized = normalize_date(date_str)
            dates_iso.append(normalized)
        except Exception as e:
            logger.warning(f"Failed to normalize date '{date_str}' for audit_index: {e}")
    
    # Add to audit_index
    audit_index['numeric_percents'] = numeric_percents
    audit_index['dates_iso'] = dates_iso
    
    return audit_index
