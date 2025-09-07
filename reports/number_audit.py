"""
Number/date audit system for LLM output validation.
Prevents hallucination by verifying all numbers exist in audit index.
"""

import re
from typing import Dict, Any, List, Tuple


class NumberAuditError(Exception):
    """Raised when number audit validation fails."""
    pass


def audit_narrative(text: str, metrics_v2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Audit narrative text against v2 audit index for hallucinations.
    
    Args:
        text: Narrative text to audit
        metrics_v2: Enhanced MetricsJSON v2 with audit_index
        
    Returns:
        Dictionary with audit results and diagnostics
    """
    audit_index = metrics_v2.get('audit_index', {})
    
    if not audit_index:
        return {
            'passed': False,
            'error': 'No audit index available',
            'hallucinated_elements': [],
            'verified_elements': []
        }
    
    # Extract elements from text
    found_percentages = _extract_percentages(text)
    found_currency = _extract_currency(text)
    found_dates = _extract_dates(text)
    found_numbers = _extract_numbers(text)
    
    # Get allowed elements from audit index
    allowed_percentages = set(audit_index.get('percent_strings', []))
    allowed_currency = set(audit_index.get('currency_strings', []))
    allowed_dates = set(audit_index.get('dates', []))
    allowed_numbers = set(audit_index.get('numbers', []))
    allowed_labels = set(audit_index.get('labels', []))
    
    # Check each found element
    hallucinated = []
    verified = []
    
    # Check percentages (with tolerance)
    for pct in found_percentages:
        if _percentage_in_allowed(pct, allowed_percentages):
            verified.append(pct)
        else:
            hallucinated.append(f"percentage: {pct}")
    
    # Check currency (exact match)
    for curr in found_currency:
        if curr in allowed_currency:
            verified.append(curr)
        else:
            hallucinated.append(f"currency: {curr}")
    
    # Check dates (flexible matching)
    for date_str in found_dates:
        if _date_in_allowed(date_str, allowed_dates):
            verified.append(date_str)
        else:
            hallucinated.append(f"date: {date_str}")
    
    # Check standalone numbers (with tolerance)
    for num in found_numbers:
        if _number_in_allowed(num, allowed_numbers):
            verified.append(str(num))
        else:
            hallucinated.append(f"number: {num}")
    
    return {
        'passed': len(hallucinated) == 0,
        'hallucinated_elements': hallucinated,
        'verified_elements': verified,
        'found_percentages': found_percentages,
        'found_currency': found_currency,
        'found_dates': found_dates,
        'found_numbers': found_numbers,
        'tolerance_applied': True
    }


def _extract_percentages(text: str) -> List[str]:
    """Extract percentage strings from text."""
    # Match percentages: -18.5%, 28.5%, etc.
    pattern = r'-?\d+\.?\d*%'
    return re.findall(pattern, text)


def _extract_currency(text: str) -> List[str]:
    """Extract currency strings from text."""
    # Match currency: $229.87, $125.0B, etc.
    pattern = r'\$\d+\.?\d*[BMK]?'
    return re.findall(pattern, text)


def _extract_dates(text: str) -> List[str]:
    """Extract date strings from text."""
    # Match "Month D, YYYY" format
    pattern = r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}'
    return re.findall(pattern, text)


def _extract_numbers(text: str) -> List[float]:
    """Extract standalone numbers from text."""
    # Match standalone numbers (not part of percentages or currency)
    # This is tricky - need to avoid double-counting
    
    # First remove percentages and currency to avoid double matches
    temp_text = re.sub(r'\$\d+\.?\d*[BMK]?', '', text)
    temp_text = re.sub(r'-?\d+\.?\d*%', '', temp_text)
    
    # Now find remaining numbers
    pattern = r'\b\d+\.?\d*\b'
    number_strings = re.findall(pattern, temp_text)
    
    numbers = []
    for num_str in number_strings:
        try:
            numbers.append(float(num_str))
        except ValueError:
            continue
    
    return numbers


def _percentage_in_allowed(found_pct: str, allowed_pcts: set) -> bool:
    """Check if percentage is in allowed set with tolerance."""
    if found_pct in allowed_pcts:
        return True
    
    # Apply tolerance (±0.1 percentage point)
    try:
        found_value = float(found_pct.replace('%', '').replace('-', ''))
        is_negative = found_pct.startswith('-')
        
        for allowed_pct in allowed_pcts:
            allowed_value = float(allowed_pct.replace('%', '').replace('-', ''))
            allowed_negative = allowed_pct.startswith('-')
            
            # Check sign consistency
            if is_negative != allowed_negative:
                continue
            
            # Check value tolerance (1.0 percentage point for reasonable rounding)
            if abs(found_value - allowed_value) <= 1.0:
                return True
        
        return False
        
    except ValueError:
        return False


def _date_in_allowed(found_date: str, allowed_dates: set) -> bool:
    """Check if date is in allowed set with flexible matching."""
    if found_date in allowed_dates:
        return True
    
    # Try case-insensitive matching
    found_lower = found_date.lower()
    for allowed_date in allowed_dates:
        if found_lower == allowed_date.lower():
            return True
    
    return False


def _number_in_allowed(found_num: float, allowed_nums: set) -> bool:
    """Check if number is in allowed set with tolerance."""
    # Direct match
    if found_num in allowed_nums:
        return True
    
    # Tolerance matching (±5% for large numbers, ±0.1 for small)
    for allowed_num in allowed_nums:
        if isinstance(allowed_num, (int, float)):
            tolerance = max(0.1, abs(allowed_num) * 0.05)  # 5% or 0.1 minimum
            if abs(found_num - allowed_num) <= tolerance:
                return True
    
    return False


def create_audit_report(audit_result: Dict[str, Any]) -> str:
    """
    Create human-readable audit report.
    
    Args:
        audit_result: Result from audit_narrative()
        
    Returns:
        Formatted audit report string
    """
    if audit_result['passed']:
        return f"✅ AUDIT PASSED\nVerified {len(audit_result['verified_elements'])} elements"
    else:
        report = ["❌ AUDIT FAILED"]
        
        if audit_result['hallucinated_elements']:
            report.append("Hallucinated elements:")
            for element in audit_result['hallucinated_elements']:
                report.append(f"  • {element}")
        
        if audit_result['verified_elements']:
            report.append(f"\nVerified elements: {len(audit_result['verified_elements'])}")
        
        return '\n'.join(report)
