"""
Report contracts and validation.
Defines report structure, LLM specifications, and validation functions.
"""

import re
from typing import Dict, Any, List


class ReportContractError(Exception):
    """Raised when report contract validation fails."""
    pass


# Required report sections in order
REQUIRED_REPORT_SECTIONS = [
    'title_block',
    'executive_summary',
    'price_snapshot', 
    'ownership_snapshot',
    'risks_watchlist',
    'appendix'
]

# LLM section specifications
LLM_SECTION_SPECS = {
    'executive_summary': {
        'word_count_min': 120,
        'word_count_max': 180,
        'format': 'single_paragraph',
        'constraints': [
            'no_bullet_points',
            'mention_drawdown',
            'mention_volatility_with_window', 
            'mention_concentration_level',
            'no_price_targets',
            'no_speculation'
        ]
    },
    'risks_watchlist': {
        'word_count_min': 50,
        'word_count_max': 200,
        'format': 'bullet_list',
        'bullet_count_min': 3,
        'bullet_count_max': 5,
        'constraints': [
            'grounded_in_metrics_only',
            'specific_numbers_with_dates',
            'no_external_context',
            'no_speculation'
        ]
    }
}


def validate_metrics_json_for_reports(metrics: Dict[str, Any]) -> None:
    """
    Validate that MetricsJSON contains required data for report generation.
    
    Args:
        metrics: Complete MetricsJSON dictionary
        
    Raises:
        ReportContractError: If required data missing
    """
    # Required top-level sections
    required_sections = [
        'ticker', 'as_of_date', 'data_period', 'price_metrics', 
        'data_quality', 'metadata'
    ]
    
    for section in required_sections:
        if section not in metrics:
            raise ReportContractError(f"Missing required section: {section}")
    
    # Validate data_period
    data_period = metrics['data_period']
    required_period_fields = ['start_date', 'end_date', 'trading_days']
    for field in required_period_fields:
        if field not in data_period:
            raise ReportContractError(f"Missing data_period field: {field}")
    
    # Validate price_metrics
    price_metrics = metrics['price_metrics']
    required_price_fields = ['returns', 'volatility', 'drawdown', 'current_price']
    for field in required_price_fields:
        if field not in price_metrics:
            raise ReportContractError(f"Missing price_metrics field: {field}")
    
    # Validate metadata
    metadata = metrics['metadata']
    required_metadata_fields = ['calculated_at', 'data_sources']
    for field in required_metadata_fields:
        if field not in metadata:
            raise ReportContractError(f"Missing metadata field: {field}")


def validate_report_structure(markdown_content: str) -> Dict[str, Dict[str, Any]]:
    """
    Validate that Markdown report has correct structure.
    
    Args:
        markdown_content: Complete Markdown report string
        
    Returns:
        Dictionary with section validation results
    """
    structure = {}
    
    # Define section patterns
    section_patterns = {
        'title_block': r'# Stock Research Report: \w+',
        'executive_summary': r'## Executive Summary',
        'price_snapshot': r'## Price Snapshot',
        'ownership_snapshot': r'## Ownership Snapshot',
        'risks_watchlist': r'## Risks & Watchlist',
        'appendix': r'## Appendix'
    }
    
    # Check each section
    for section_name, pattern in section_patterns.items():
        match = re.search(pattern, markdown_content)
        structure[section_name] = {
            'found': match is not None,
            'position': match.start() if match else -1
        }
    
    # Check section ordering
    found_sections = [
        (name, info['position']) for name, info in structure.items() 
        if info['found']
    ]
    found_sections.sort(key=lambda x: x[1])
    
    # Verify order matches required order
    found_names = [name for name, _ in found_sections]
    expected_order = [s for s in REQUIRED_REPORT_SECTIONS if s in found_names]
    
    structure['_order_correct'] = found_names == expected_order
    structure['_missing_sections'] = [
        s for s in REQUIRED_REPORT_SECTIONS 
        if not structure.get(s, {}).get('found', False)
    ]
    
    return structure


def validate_llm_output(
    section_name: str,
    content: str,
    metrics: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate LLM-generated content against contracts and metrics.
    
    Args:
        section_name: Name of the section (executive_summary, risks_watchlist)
        content: LLM-generated content
        metrics: Source MetricsJSON for number auditing
        
    Returns:
        Dictionary with validation results
    """
    if section_name not in LLM_SECTION_SPECS:
        raise ReportContractError(f"Unknown LLM section: {section_name}")
    
    spec = LLM_SECTION_SPECS[section_name]
    results = {
        'section': section_name,
        'valid': True,
        'warnings': [],
        'errors': []
    }
    
    # Word count validation
    word_count = len(content.split())
    min_words = spec['word_count_min']
    max_words = spec['word_count_max']
    
    if word_count < min_words:
        results['errors'].append(f"Too short: {word_count} words (min: {min_words})")
        results['valid'] = False
    elif word_count > max_words:
        results['errors'].append(f"Too long: {word_count} words (max: {max_words})")
        results['valid'] = False
    
    # Format validation
    if spec['format'] == 'bullet_list':
        bullets = re.findall(r'^\s*[-*•]\s+', content, re.MULTILINE)
        bullet_count = len(bullets)
        
        min_bullets = spec.get('bullet_count_min', 1)
        max_bullets = spec.get('bullet_count_max', 10)
        
        if bullet_count < min_bullets:
            results['errors'].append(f"Too few bullets: {bullet_count} (min: {min_bullets})")
            results['valid'] = False
        elif bullet_count > max_bullets:
            results['errors'].append(f"Too many bullets: {bullet_count} (max: {max_bullets})")
            results['valid'] = False
    
    # Number audit - check that all numbers in content exist in metrics
    number_audit = audit_numbers_in_content(content, metrics)
    if number_audit['hallucinated_numbers']:
        results['errors'].extend([
            f"Hallucinated number: {num}" for num in number_audit['hallucinated_numbers']
        ])
        results['valid'] = False
    
    if number_audit['unverified_dates']:
        results['warnings'].extend([
            f"Unverified date: {date}" for date in number_audit['unverified_dates']
        ])
    
    return results


def audit_numbers_in_content(content: str, metrics: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Audit all numbers in content against MetricsJSON.
    
    Args:
        content: Text content to audit
        metrics: Source MetricsJSON
        
    Returns:
        Dictionary with audit results
    """
    # Extract all numbers from content
    number_patterns = [
        r'\d+\.?\d*%',  # Percentages
        r'\$\d+\.?\d*[BMK]?',  # Currency
        r'\b\d+\.?\d+\b',  # General numbers
    ]
    
    found_numbers = []
    for pattern in number_patterns:
        matches = re.findall(pattern, content)
        found_numbers.extend(matches)
    
    # Extract all dates from content
    date_pattern = r'\d{4}-\d{2}-\d{2}'
    found_dates = re.findall(date_pattern, content)
    
    # Flatten metrics to find all numbers and dates
    metrics_numbers = _extract_all_numbers_from_metrics(metrics)
    metrics_dates = _extract_all_dates_from_metrics(metrics)
    
    # Check each found number
    hallucinated_numbers = []
    for num_str in found_numbers:
        if not _number_exists_in_metrics(num_str, metrics_numbers):
            hallucinated_numbers.append(num_str)
    
    # Check each found date
    unverified_dates = []
    for date_str in found_dates:
        if date_str not in metrics_dates:
            unverified_dates.append(date_str)
    
    return {
        'found_numbers': found_numbers,
        'found_dates': found_dates,
        'hallucinated_numbers': hallucinated_numbers,
        'unverified_dates': unverified_dates
    }


def _extract_all_numbers_from_metrics(metrics: Dict[str, Any]) -> List[float]:
    """Extract all numeric values from MetricsJSON."""
    numbers = []
    
    def extract_recursive(obj):
        if isinstance(obj, dict):
            for value in obj.values():
                extract_recursive(value)
        elif isinstance(obj, list):
            for item in obj:
                extract_recursive(item)
        elif isinstance(obj, (int, float)):
            numbers.append(float(obj))
    
    extract_recursive(metrics)
    return numbers


def _extract_all_dates_from_metrics(metrics: Dict[str, Any]) -> List[str]:
    """Extract all date strings from MetricsJSON."""
    dates = []
    
    def extract_recursive(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if 'date' in key.lower() and isinstance(value, str):
                    if re.match(r'\d{4}-\d{2}-\d{2}', value):
                        dates.append(value)
                extract_recursive(value)
        elif isinstance(obj, list):
            for item in obj:
                extract_recursive(item)
    
    extract_recursive(metrics)
    return dates


def _number_exists_in_metrics(num_str: str, metrics_numbers: List[float]) -> bool:
    """Check if a number string exists in metrics (with tolerance)."""
    # Parse number from string
    try:
        # Handle percentages
        if '%' in num_str:
            num_val = float(num_str.replace('%', '')) / 100
        # Handle currency
        elif '$' in num_str:
            clean_num = num_str.replace('$', '').replace(',', '')
            if 'B' in clean_num:
                num_val = float(clean_num.replace('B', '')) * 1e9
            elif 'M' in clean_num:
                num_val = float(clean_num.replace('M', '')) * 1e6
            elif 'K' in clean_num:
                num_val = float(clean_num.replace('K', '')) * 1e3
            else:
                num_val = float(clean_num)
        else:
            num_val = float(num_str)
        
        # Check if this number exists in metrics (with 0.1% tolerance)
        for metrics_num in metrics_numbers:
            if abs(num_val - metrics_num) / max(abs(metrics_num), 1e-10) < 0.001:
                return True
        
        return False
        
    except (ValueError, ZeroDivisionError):
        return False  # Could not parse number
