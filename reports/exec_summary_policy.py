"""
Executive summary policy validation and fixture loading.
Contract enforcement for quantitative-only summaries.
"""

from pathlib import Path
from typing import Dict, Any


class ExecSummaryPolicyError(Exception):
    """Raised when executive summary policy validation fails."""
    pass


def validate_exec_summary_contract(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that MetricsJSON contains sufficient data for executive summary.
    
    Args:
        metrics: Complete MetricsJSON dictionary
        
    Returns:
        Dictionary with validation results
        
    Raises:
        ExecSummaryPolicyError: If required fields missing
    """
    # Required top-level fields
    required_fields = ['ticker', 'as_of_date', 'price_metrics']
    for field in required_fields:
        if field not in metrics:
            raise ExecSummaryPolicyError(f"Missing required field: {field}")
    
    price_metrics = metrics['price_metrics']
    institutional_metrics = metrics.get('institutional_metrics')
    
    # Analyze data availability
    validation = {
        'valid': True,
        'ticker': metrics['ticker'],
        'as_of_date': metrics['as_of_date'],
        'has_price_metrics': True,
        'has_institutional_metrics': institutional_metrics is not None,
        'has_volatility': False,
        'has_drawdown': False,
        'has_concentration': False,
        'data_sufficiency': 'minimal'
    }
    
    # Check volatility data
    volatility = price_metrics.get('volatility', {})
    if any(v is not None for v in volatility.values()):
        validation['has_volatility'] = True
    
    # Check drawdown data
    drawdown = price_metrics.get('drawdown', {})
    if drawdown.get('max_drawdown_pct') is not None:
        validation['has_drawdown'] = True
    
    # Check concentration data
    if institutional_metrics:
        concentration = institutional_metrics.get('concentration', {})
        if any(v is not None for v in concentration.values()):
            validation['has_concentration'] = True
    
    # Determine data sufficiency level
    data_elements = sum([
        validation['has_volatility'],
        validation['has_drawdown'], 
        validation['has_concentration']
    ])
    
    if data_elements >= 3:
        validation['data_sufficiency'] = 'complete'
    elif data_elements >= 2:
        validation['data_sufficiency'] = 'good'
    elif data_elements >= 1:
        validation['data_sufficiency'] = 'basic'
    else:
        validation['data_sufficiency'] = 'minimal'
    
    return validation


def load_skeleton_fixture(ticker_key: str) -> str:
    """
    Load skeleton fixture for testing.
    
    Args:
        ticker_key: Fixture key (e.g., 'aapl', 'msft')
        
    Returns:
        Skeleton text content
    """
    fixture_path = Path(__file__).parent.parent / 'tests/fixtures/golden' / f'{ticker_key}_exec_summary_skeleton.txt'
    
    if not fixture_path.exists():
        raise ExecSummaryPolicyError(f"Skeleton fixture not found: {fixture_path}")
    
    with open(fixture_path, 'r') as f:
        return f.read().strip()


def validate_skeleton_quality(skeleton: str) -> Dict[str, Any]:
    """
    Validate skeleton quality against policy.
    
    Args:
        skeleton: Skeleton text to validate
        
    Returns:
        Dictionary with quality assessment
    """
    words = skeleton.split()
    word_count = len(words)
    
    quality = {
        'word_count': word_count,
        'word_count_valid': 120 <= word_count <= 180,
        'has_percentages': '%' in skeleton,
        'has_dates': any(str(year) in skeleton for year in range(2020, 2030)),
        'has_windows': '(' in skeleton and ')' in skeleton,
        'mentions_volatility': 'volatility' in skeleton.lower() or 'vol' in skeleton.lower(),
        'mentions_drawdown': 'drawdown' in skeleton.lower() or 'decline' in skeleton.lower(),
        'mentions_concentration': 'concentration' in skeleton.lower(),
        'speculative_words': []
    }
    
    # Check for speculative language
    prohibited_words = ['will', 'should', 'expect', 'likely', 'probably', 'may', 'might', 'could', 'target', 'forecast']
    skeleton_lower = skeleton.lower()
    
    for word in prohibited_words:
        if word in skeleton_lower:
            quality['speculative_words'].append(word)
    
    # Overall quality score
    quality_checks = [
        quality['word_count_valid'],
        quality['has_percentages'],
        quality['has_dates'],
        quality['mentions_volatility'],
        quality['mentions_drawdown'],
        len(quality['speculative_words']) == 0
    ]
    
    quality['quality_score'] = sum(quality_checks) / len(quality_checks)
    quality['passes_policy'] = quality['quality_score'] >= 0.8  # 80% of checks pass
    
    return quality


def extract_data_elements_from_skeleton(skeleton: str) -> Dict[str, Any]:
    """
    Extract data elements from skeleton for verification.
    
    Args:
        skeleton: Skeleton text
        
    Returns:
        Dictionary with extracted elements
    """
    import re
    
    # Extract percentages
    percentages = re.findall(r'-?\d+\.?\d*%', skeleton)
    
    # Extract dates (Month D, YYYY format)
    date_patterns = [
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}',
        r'\d{4}-\d{2}-\d{2}'  # ISO format as fallback
    ]
    
    dates = []
    for pattern in date_patterns:
        dates.extend(re.findall(pattern, skeleton))
    
    # Extract currency amounts
    currency = re.findall(r'\$\d+\.?\d*[BMK]?', skeleton)
    
    # Extract windows
    windows = re.findall(r'\(\d+-day\)', skeleton)
    
    return {
        'percentages': percentages,
        'dates': dates,
        'currency_amounts': currency,
        'windows': windows,
        'total_data_points': len(percentages) + len(dates) + len(currency) + len(windows)
    }
