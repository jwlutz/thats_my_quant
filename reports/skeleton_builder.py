"""
Executive summary skeleton builder.
Builds data-filled paragraph with all numbers pre-filled from Enhanced MetricsJSON v2.
"""

from typing import Dict, Any


class SkeletonBuilderError(Exception):
    """Raised when skeleton building fails."""
    pass


def build_exec_summary_skeleton(metrics_v2: Dict[str, Any]) -> str:
    """
    Build executive summary skeleton with all data pre-filled.
    
    Args:
        metrics_v2: Enhanced MetricsJSON v2 dictionary
        
    Returns:
        Complete paragraph with all numbers/dates from v2 data
        
    Raises:
        SkeletonBuilderError: If required data missing
    """
    if not metrics_v2 or 'meta' not in metrics_v2:
        raise SkeletonBuilderError("Invalid v2 metrics provided")
    
    ticker = metrics_v2['meta']['ticker']
    company = metrics_v2['meta'].get('company', f"{ticker} Inc.")
    
    # Build skeleton components
    components = []
    
    # Opening statement with current price
    components.append(_build_opening_statement(ticker, company, metrics_v2['price']))
    
    # Returns performance
    returns_text = _build_returns_statement(metrics_v2['price']['returns'])
    if returns_text:
        components.append(returns_text)
    
    # Volatility statement
    vol_text = _build_volatility_statement(metrics_v2['price']['volatility'])
    components.append(vol_text)
    
    # Drawdown statement
    dd_text = _build_drawdown_statement(metrics_v2['price']['drawdown'])
    components.append(dd_text)
    
    # Institutional ownership
    ownership_text = _build_ownership_statement(metrics_v2.get('ownership_13f'))
    components.append(ownership_text)
    
    # Data quality note
    dq_text = _build_data_quality_note(metrics_v2.get('data_quality', {}))
    if dq_text:
        components.append(dq_text)
    
    # Join components into paragraph
    skeleton = ' '.join(comp for comp in components if comp)
    
    # Ensure word count is within bounds
    words = skeleton.split()
    if len(words) > 180:
        # Truncate at sentence boundary near 180 words
        skeleton = _truncate_at_sentence(skeleton, 180)
    elif len(words) < 120:
        # Add context to reach minimum
        skeleton = _expand_with_context(skeleton, metrics_v2)
    
    return skeleton


def _build_opening_statement(ticker: str, company: str, price_data: Dict[str, Any]) -> str:
    """Build opening statement with current price."""
    current = price_data.get('current', {})
    current_price = current.get('display', 'Not available')
    current_date = current.get('date_display', 'Not available')
    
    return f"{company} ({ticker}) closed at {current_price} as of {current_date}."


def _build_returns_statement(returns_data: Dict[str, Any]) -> str:
    """Build returns performance statement."""
    display = returns_data.get('display', {})
    
    # Find best available return periods for summary
    periods_priority = ['1M', '3M', '6M', '1Y', '1W', '1D']
    mentioned_periods = []
    
    for period in periods_priority:
        if period in display and display[period] != "Not available":
            period_name = _format_period_name(period)
            mentioned_periods.append(f"{display[period]} ({period_name})")
            
            # Limit to 2-3 periods for readability
            if len(mentioned_periods) >= 3:
                break
    
    if mentioned_periods:
        if len(mentioned_periods) == 1:
            return f"The stock returned {mentioned_periods[0]}."
        else:
            periods_text = ", ".join(mentioned_periods[:-1]) + f", and {mentioned_periods[-1]}"
            return f"Returns were {periods_text}."
    else:
        return "Return data not available."


def _build_volatility_statement(volatility_data: Dict[str, Any]) -> str:
    """Build volatility statement."""
    vol_display = volatility_data.get('display', 'Not available')
    vol_level = volatility_data.get('level', 'unknown')
    vol_window = volatility_data.get('window_display', '(21-day)')
    
    if vol_display == "Not available":
        return "Volatility data not available."
    else:
        return f"The stock exhibited {vol_level} volatility of {vol_display} {vol_window}."


def _build_drawdown_statement(drawdown_data: Dict[str, Any]) -> str:
    """Build drawdown and recovery statement."""
    max_dd = drawdown_data.get('max_dd_display', 'Not available')
    
    if max_dd == "Not available":
        return "Drawdown analysis not available."
    
    peak_date = drawdown_data.get('peak_date_display')
    trough_date = drawdown_data.get('trough_date_display')
    recovery_status = drawdown_data.get('recovery_status', 'recovery status unknown')
    
    if peak_date and trough_date:
        return f"The stock experienced a maximum drawdown of {max_dd} from {peak_date} to {trough_date}, {recovery_status}."
    else:
        return f"The stock experienced a maximum drawdown of {max_dd}."


def _build_ownership_statement(ownership_data: Dict[str, Any]) -> str:
    """Build institutional ownership statement."""
    if not ownership_data:
        return "Institutional ownership data not available."
    
    concentration = ownership_data.get('concentration', {})
    level = concentration.get('level', 'unknown')
    basis = concentration.get('basis', 'unknown')
    
    total_value = ownership_data.get('total_value', {})
    total_display = total_value.get('display', 'Not available')
    total_holders = ownership_data.get('total_holders', 0)
    
    # Build concentration statement
    if level != 'unknown' and basis != 'unknown':
        if basis == 'CR5' and 'cr5' in concentration:
            cr5_display = concentration['cr5'].get('display', 'Not available')
            conc_text = f"Institutional ownership shows {level} concentration based on {basis} with top 5 holders controlling {cr5_display}"
        elif basis == 'HHI' and 'hhi' in concentration:
            hhi_display = concentration['hhi'].get('display', 'Not available')
            conc_text = f"Institutional ownership shows {level} concentration based on {basis} ({hhi_display})"
        else:
            conc_text = f"Institutional ownership shows {level} concentration"
    else:
        conc_text = "Institutional ownership concentration not available"
    
    # Add total value context
    if total_display != "Not available" and total_holders > 0:
        conc_text += f" across {total_holders} institutions totaling {total_display}."
    else:
        conc_text += "."
    
    return conc_text


def _build_data_quality_note(data_quality: Dict[str, Any]) -> str:
    """Build data quality note if relevant."""
    coverage = data_quality.get('price_coverage', {})
    coverage_display = coverage.get('display')
    missing_days = data_quality.get('missing_days', 0)
    
    if coverage_display and coverage_display != "Not available":
        if missing_days > 0:
            return f"Analysis covers {coverage_display} of expected trading days with {missing_days} missing days."
        else:
            return f"Price data coverage is {coverage_display}."
    
    return None  # No quality note needed


def _format_period_name(period_key: str) -> str:
    """Convert period key to readable name."""
    period_map = {
        '1D': '1-day',
        '1W': '1-week',
        '1M': '1-month', 
        '3M': '3-month',
        '6M': '6-month',
        '1Y': '1-year'
    }
    return period_map.get(period_key, period_key)


def _truncate_at_sentence(text: str, max_words: int) -> str:
    """Truncate text at sentence boundary near max_words."""
    words = text.split()
    if len(words) <= max_words:
        return text
    
    # Find last sentence end before max_words
    truncated_words = words[:max_words]
    truncated_text = ' '.join(truncated_words)
    
    # Find last sentence boundary
    last_period = truncated_text.rfind('.')
    if last_period > 0:
        return truncated_text[:last_period + 1]
    else:
        # No sentence boundary found, hard truncate
        return truncated_text + '...'


def _expand_with_context(skeleton: str, metrics_v2: Dict[str, Any]) -> str:
    """Expand skeleton with additional context to reach minimum words."""
    words = skeleton.split()
    if len(words) >= 120:
        return skeleton
    
    # Add additional context
    additional_context = []
    
    # Add data period context
    data_period = metrics_v2.get('data_period', {})
    trading_days = data_period.get('trading_days')
    if trading_days:
        additional_context.append(f"The analysis spans {trading_days} trading days of data.")
    
    # Add source context
    sources = metrics_v2['meta'].get('sources', [])
    if sources:
        source_text = ', '.join(sources)
        additional_context.append(f"Data sourced from {source_text}.")
    
    # Join with original skeleton
    if additional_context:
        expanded = skeleton + ' ' + ' '.join(additional_context)
        return expanded
    
    return skeleton
