"""
Enhanced MetricsJSON v2 schema validation.
Validates structure, consistency, and audit index completeness.
"""

from typing import Dict, Any


class V2SchemaError(Exception):
    """Raised when v2 schema validation fails."""
    pass


SCHEMA_VERSION_V2 = "2.0.0"


def validate_v2_schema(metrics_v2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate Enhanced MetricsJSON v2 schema.
    
    Args:
        metrics_v2: Enhanced MetricsJSON v2 dictionary
        
    Returns:
        Dictionary with validation results
        
    Raises:
        V2SchemaError: If schema validation fails
    """
    # Required top-level sections
    required_sections = ['meta', 'price', 'audit_index']
    for section in required_sections:
        if section not in metrics_v2:
            raise V2SchemaError(f"Missing required section: {section}")
    
    # Validate meta section
    meta = metrics_v2['meta']
    if meta.get('schema_version') != SCHEMA_VERSION_V2:
        raise V2SchemaError(f"Invalid schema version: {meta.get('schema_version')}")
    
    # Validate audit index structure
    audit_index = metrics_v2['audit_index']
    if not isinstance(audit_index, dict):
        raise V2SchemaError("audit_index must be dict")
    
    required_audit_categories = [
        'percent_strings', 'currency_strings', 'dates',
        'labels', 'numbers', 'windows'
    ]
    
    for category in required_audit_categories:
        if category not in audit_index:
            raise V2SchemaError(f"Missing audit index category: {category}")
        if not isinstance(audit_index[category], list):
            raise V2SchemaError(f"Audit index {category} must be list")
    
    # Build validation result
    validation = {
        'valid': True,
        'schema_version': meta['schema_version'],
        'ticker': meta.get('ticker'),
        'has_meta': True,
        'has_price': 'price' in metrics_v2,
        'has_ownership': 'ownership_13f' in metrics_v2,
        'has_audit_index': True,
        'audit_categories': list(audit_index.keys())
    }
    
    # Validate price section structure
    if validation['has_price']:
        price = metrics_v2['price']
        validation['price_sections'] = list(price.keys())
        
        # Check for raw/display pairs
        if 'returns' in price:
            returns = price['returns']
            validation['has_returns_raw'] = 'raw' in returns
            validation['has_returns_display'] = 'display' in returns
        
        if 'volatility' in price:
            volatility = price['volatility']
            validation['has_volatility_raw'] = 'raw' in volatility
            validation['has_volatility_display'] = 'display' in volatility
            validation['has_volatility_level'] = 'level' in volatility
    
    # Validate ownership section structure
    if validation['has_ownership']:
        ownership = metrics_v2['ownership_13f']
        concentration = ownership.get('concentration', {})
        validation['concentration_basis'] = concentration.get('basis')
        validation['concentration_level'] = concentration.get('level')
    
    return validation


def validate_audit_index_completeness(metrics_v2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate that audit index contains all display values from the metrics.
    
    Args:
        metrics_v2: Enhanced MetricsJSON v2 dictionary
        
    Returns:
        Dictionary with completeness check results
    """
    audit_index = metrics_v2.get('audit_index', {})
    
    # Extract all display values from metrics
    found_percentages = []
    found_currency = []
    found_dates = []
    
    def extract_display_values(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == 'display' and isinstance(value, str):
                    if '%' in value:
                        found_percentages.append(value)
                    elif '$' in value:
                        found_currency.append(value)
                elif 'date_display' in key and isinstance(value, str):
                    found_dates.append(value)
                else:
                    extract_display_values(value, f"{path}.{key}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                extract_display_values(item, f"{path}[{i}]")
    
    extract_display_values(metrics_v2)
    
    # Check completeness
    audit_percentages = set(audit_index.get('percent_strings', []))
    audit_currency = set(audit_index.get('currency_strings', []))
    audit_dates = set(audit_index.get('dates', []))
    
    missing_percentages = set(found_percentages) - audit_percentages
    missing_currency = set(found_currency) - audit_currency
    missing_dates = set(found_dates) - audit_dates
    
    return {
        'complete': len(missing_percentages) == 0 and len(missing_currency) == 0 and len(missing_dates) == 0,
        'found_percentages': found_percentages,
        'found_currency': found_currency,
        'found_dates': found_dates,
        'missing_percentages': list(missing_percentages),
        'missing_currency': list(missing_currency),
        'missing_dates': list(missing_dates),
        'audit_coverage_pct': len(audit_percentages | audit_currency | audit_dates) / max(1, len(found_percentages) + len(found_currency) + len(found_dates)) * 100
    }


def validate_v2_consistency(metrics_v2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate internal consistency of v2 metrics.
    
    Args:
        metrics_v2: Enhanced MetricsJSON v2 dictionary
        
    Returns:
        Dictionary with consistency check results
    """
    consistency = {
        'consistent': True,
        'errors': [],
        'warnings': []
    }
    
    # Check raw/display consistency in price metrics
    price = metrics_v2.get('price', {})
    
    # Returns consistency
    returns = price.get('returns', {})
    if 'raw' in returns and 'display' in returns:
        for period in returns['raw']:
            raw_val = returns['raw'][period]
            display_val = returns['display'][period]
            
            if raw_val is not None and display_val != 'Not available':
                # Calculate expected display
                expected_display = f"{raw_val * 100:.1f}%"
                if raw_val < 0:
                    expected_display = f"-{abs(raw_val * 100):.1f}%"
                
                if display_val != expected_display:
                    consistency['errors'].append(
                        f"Returns {period}: raw {raw_val} → display '{display_val}' (expected '{expected_display}')"
                    )
                    consistency['consistent'] = False
    
    # Volatility consistency
    volatility = price.get('volatility', {})
    if 'raw' in volatility and 'display' in volatility:
        vol_raw = volatility['raw']
        vol_display = volatility['display']
        expected_vol_display = f"{vol_raw * 100:.1f}%"
        
        if vol_display != expected_vol_display:
            consistency['errors'].append(
                f"Volatility: raw {vol_raw} → display '{vol_display}' (expected '{expected_vol_display}')"
            )
            consistency['consistent'] = False
    
    return consistency
