"""
v1→v2 Builder - convert existing MetricsJSON to Enhanced v2 format.
Applies labelers and formatters, builds audit index.
"""

import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

# Import labelers and formatters
from reports.labelers import (
    classify_vol_level,
    classify_concentration,
    classify_drawdown_severity,
    classify_return_performance
)
from reports.formatters import (
    format_percentage,
    format_currency,
    format_date_display,
    format_window_display,
    format_recovery_status,
    build_audit_index_entry
)


class V1ToV2BuilderError(Exception):
    """Raised when v1 to v2 conversion fails."""
    pass


def build_enhanced_metrics_v2(metrics_v1: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert MetricsJSON v1 to Enhanced v2 format.
    
    Args:
        metrics_v1: Original MetricsJSON from analysis engine
        
    Returns:
        Enhanced MetricsJSON v2 with display values and audit index
        
    Raises:
        V1ToV2BuilderError: If conversion fails
    """
    if not metrics_v1:
        raise V1ToV2BuilderError("Empty v1 metrics provided")
    
    # Required v1 fields
    required_fields = ['ticker', 'as_of_date', 'price_metrics', 'metadata']
    for field in required_fields:
        if field not in metrics_v1:
            raise V1ToV2BuilderError(f"Missing required v1 field: {field}")
    
    # Build v2 structure
    v2_metrics = {
        'meta': _build_meta_section(metrics_v1),
        'price': _build_price_section(metrics_v1['price_metrics'], metrics_v1['as_of_date']),
        'data_quality': _build_data_quality_section(metrics_v1.get('data_quality', {})),
        'footnotes': [
            "Volatility annualized with √252.",
            "No back-adjustment of OHLCV; adj_close reported if available.",
            "13F data has 45-day regulatory filing lag."
        ]
    }
    
    # Add ownership section if available
    if metrics_v1.get('institutional_metrics'):
        v2_metrics['ownership_13f'] = _build_ownership_section(metrics_v1['institutional_metrics'])
    
    # Build audit index from all display values
    v2_metrics['audit_index'] = _build_audit_index(v2_metrics)
    
    return v2_metrics


def _build_meta_section(metrics_v1: Dict[str, Any]) -> Dict[str, Any]:
    """Build meta section for v2."""
    metadata = metrics_v1['metadata']
    
    # Get timezone from environment or default
    timezone_name = os.getenv('REPORTS_TZ', 'America/Los_Angeles')
    
    # Create local timestamp
    as_of_date = metrics_v1['as_of_date']
    if isinstance(as_of_date, str):
        # Assume end of day for as_of date
        local_dt = datetime.fromisoformat(f"{as_of_date}T15:00:00")
    else:
        local_dt = datetime.combine(as_of_date, datetime.min.time())
    
    # Create UTC timestamp
    utc_dt = datetime.now(timezone.utc)
    
    return {
        'ticker': metrics_v1['ticker'],
        'company': f"{metrics_v1['ticker']} Inc.",  # Simple default
        'exchange': 'NASDAQ',  # Default for US stocks
        'currency': 'USD',
        'as_of_local': f"{local_dt.isoformat()}-07:00",  # Assume PST for now
        'as_of_utc': utc_dt.isoformat(),
        'timezone': timezone_name,
        'run_id': metadata.get('run_id'),
        'sources': metadata.get('data_sources', []),
        'schema_version': '2.0.0'
    }


def _build_price_section(price_metrics: Dict[str, Any], as_of_date: str) -> Dict[str, Any]:
    """Build price section for v2."""
    # Current price
    current_price = price_metrics.get('current_price', {})
    current_section = {
        'value': current_price.get('close'),
        'display': format_currency(current_price.get('close')) if current_price.get('close') else "Not available",
        'date': current_price.get('date'),
        'date_display': format_date_display(current_price.get('date')) if current_price.get('date') else "Not available"
    }
    
    # Returns
    returns_v1 = price_metrics.get('returns', {})
    returns_raw = {}
    returns_display = {}
    
    for period, value in returns_v1.items():
        returns_raw[period] = value
        returns_display[period] = format_percentage(value) if value is not None else "Not available"
    
    returns_section = {
        'windows': list(returns_raw.keys()),
        'raw': returns_raw,
        'display': returns_display
    }
    
    # Add performance classification
    perf_class = classify_return_performance(returns_raw)
    returns_section.update(perf_class)
    
    # Volatility
    volatility_v1 = price_metrics.get('volatility', {})
    vol_21d = volatility_v1.get('21D_annualized')
    
    volatility_section = {
        'window_days': 21,
        'raw': vol_21d,
        'display': format_percentage(vol_21d) if vol_21d is not None else "Not available",
        'level': classify_vol_level(vol_21d) if vol_21d is not None else "unknown",
        'window_display': "(21-day)"
    }
    
    # Drawdown
    drawdown_v1 = price_metrics.get('drawdown', {})
    max_dd = drawdown_v1.get('max_drawdown_pct')
    
    drawdown_section = {
        'max_dd_raw': max_dd,
        'max_dd_display': f"-{abs(max_dd * 100):.1f}%" if max_dd is not None else "Not available",
        'peak_date': drawdown_v1.get('peak_date'),
        'peak_date_display': format_date_display(drawdown_v1.get('peak_date')),
        'trough_date': drawdown_v1.get('trough_date'),
        'trough_date_display': format_date_display(drawdown_v1.get('trough_date')),
        'recovery_date': drawdown_v1.get('recovery_date'),
        'recovery_date_display': format_date_display(drawdown_v1.get('recovery_date')) if drawdown_v1.get('recovery_date') else None,
        'recovered': drawdown_v1.get('recovery_date') is not None,
        'duration_days': drawdown_v1.get('drawdown_days'),
        'recovery_status': format_recovery_status(drawdown_v1.get('recovery_date'), as_of_date)
    }
    
    return {
        'current': current_section,
        'returns': returns_section,
        'volatility': volatility_section,
        'drawdown': drawdown_section
    }


def _build_ownership_section(institutional_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Build ownership_13f section for v2."""
    concentration_v1 = institutional_metrics.get('concentration', {})
    
    # Classify concentration
    conc_class = classify_concentration(concentration_v1)
    
    # Build concentration section
    concentration_section = {
        'basis': conc_class['basis'],
        'level': conc_class['level']
    }
    
    # Add raw and display values
    for metric in ['cr1', 'cr5', 'cr10', 'hhi']:
        if metric in concentration_v1 and concentration_v1[metric] is not None:
            concentration_section[metric] = {
                'raw': concentration_v1[metric],
                'display': format_percentage(concentration_v1[metric]) if metric != 'hhi' else f"{concentration_v1[metric]:.3f}"
            }
    
    # Top holders
    top_holders_v1 = institutional_metrics.get('top_holders', [])
    top_holders_v2 = []
    
    for holder in top_holders_v1:
        holder_v2 = {
            'rank': holder.get('rank'),
            'filer': holder.get('filer'),
            'value_raw': holder.get('value_usd'),
            'value_display': format_currency(holder.get('value_usd')),
            'share_of_total_raw': holder.get('pct_of_13f_total'),
            'share_of_total_display': format_percentage(holder.get('pct_of_13f_total'))
        }
        top_holders_v2.append(holder_v2)
    
    return {
        'as_of': institutional_metrics.get('quarter_end'),
        'as_of_display': format_date_display(institutional_metrics.get('quarter_end')),
        'total_value': {
            'raw': institutional_metrics.get('total_13f_value_usd'),
            'display': format_currency(institutional_metrics.get('total_13f_value_usd'))
        },
        'total_holders': institutional_metrics.get('total_13f_holders'),
        'concentration': concentration_section,
        'top_holders': top_holders_v2,
        'disclaimer': "13F reflects reported long U.S. positions with reporting lag; not total float."
    }


def _build_data_quality_section(data_quality_v1: Dict[str, Any]) -> Dict[str, Any]:
    """Build data quality section for v2."""
    coverage_pct = data_quality_v1.get('price_coverage_pct')
    
    return {
        'price_coverage': {
            'raw': coverage_pct / 100 if coverage_pct is not None else None,
            'display': f"{coverage_pct:.1f}%" if coverage_pct is not None else "Not available"
        },
        'missing_days': data_quality_v1.get('missing_price_days', 0),
        '13f_age_days': data_quality_v1.get('13f_data_age_days'),
        'limitations': ['quarterly_13f_lag', 'weekend_gaps_normal']
    }


def _build_audit_index(v2_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build comprehensive audit index from v2 metrics.
    
    Args:
        v2_metrics: Complete v2 metrics dictionary
        
    Returns:
        Audit index with all allowed narrative elements
    """
    audit_index = {
        'percent_strings': [],
        'currency_strings': [],
        'dates': [],
        'labels': [],
        'numbers': [],
        'windows': []
    }
    
    def extract_values(obj, path=""):
        """Recursively extract values for audit index."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key == 'display' and isinstance(value, str) and value != "Not available":
                    if '%' in value:
                        audit_index['percent_strings'].append(value)
                    elif '$' in value:
                        audit_index['currency_strings'].append(value)
                elif 'date_display' in key and isinstance(value, str) and value != "Not available":
                    audit_index['dates'].append(value)
                elif key == 'level' and isinstance(value, str):
                    audit_index['labels'].append(value)
                elif key == 'basis' and isinstance(value, str):
                    audit_index['labels'].append(value)
                elif key in ['window_display', 'recovery_status'] and isinstance(value, str):
                    if '(' in value and ')' in value:
                        audit_index['windows'].append(value)
                    else:
                        audit_index['labels'].append(value)
                else:
                    extract_values(value, f"{path}.{key}")
        elif isinstance(obj, list):
            for item in obj:
                extract_values(item, path)
    
    # Extract all values
    extract_values(v2_metrics)
    
    # Deduplicate and sort each category
    for category in audit_index:
        audit_index[category] = build_audit_index_entry(audit_index[category], category)
    
    return audit_index
