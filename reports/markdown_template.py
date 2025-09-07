"""
Markdown template for rendering MetricsJSON to human-readable reports.
Pure function - no I/O, just template rendering.
"""

from datetime import datetime
from typing import Dict, Any, Optional


class TemplateError(Exception):
    """Raised when template rendering fails."""
    pass


def render_metrics_report(metrics: Dict[str, Any]) -> str:
    """
    Render MetricsJSON to formatted Markdown report.
    
    Args:
        metrics: Complete MetricsJSON dictionary
        
    Returns:
        Formatted Markdown string
        
    Raises:
        TemplateError: If rendering fails
    """
    if not metrics:
        raise TemplateError("Empty or invalid metrics provided")
    
    # Validate required fields
    required_fields = ['ticker', 'as_of_date', 'price_metrics', 'data_quality', 'metadata']
    for field in required_fields:
        if field not in metrics:
            raise TemplateError(f"Missing required field: {field}")
    
    # Validate data structures
    if not isinstance(metrics['price_metrics'], dict):
        raise TemplateError("Invalid data structure: price_metrics must be dict")
    
    ticker = metrics['ticker']
    as_of_date = metrics['as_of_date']
    
    # Build report sections
    report_sections = [
        _render_header(ticker, as_of_date, metrics.get('data_period', {})),
        _render_price_metrics(metrics['price_metrics']),
        _render_institutional_metrics(metrics.get('institutional_metrics')),
        _render_data_quality(metrics['data_quality']),
        _render_footer(metrics['metadata'])
    ]
    
    return '\n\n'.join(section for section in report_sections if section)


def _render_header(ticker: str, as_of_date: str, data_period: dict) -> str:
    """Render report header with metadata."""
    trading_days = data_period.get('trading_days', 0)
    start_date = data_period.get('start_date', 'Unknown')
    end_date = data_period.get('end_date', 'Unknown')
    
    return f"""# Stock Analysis Report: {ticker}

**Analysis Date:** {as_of_date}  
**Data Period:** {start_date} to {end_date} ({trading_days} trading days)  
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---"""


def _render_price_metrics(price_metrics: dict) -> str:
    """Render price metrics section."""
    sections = ["## Price Metrics"]
    
    # Current price
    current = price_metrics.get('current_price', {})
    if current:
        price = format_currency(current.get('close'))
        date_str = current.get('date', 'Unknown')
        sections.append(f"**Current Price:** {price} (as of {date_str})")
    
    # Returns table
    returns = price_metrics.get('returns', {})
    if any(v is not None for v in returns.values()):
        sections.append("### Returns")
        sections.append("| Period | Return |")
        sections.append("|--------|--------|")
        
        for period, label in [('1D', '1 Day'), ('1W', '1 Week'), ('1M', '1 Month'), 
                             ('3M', '3 Month'), ('6M', '6 Month'), ('1Y', '1 Year')]:
            value = returns.get(period)
            formatted = format_percentage(value, show_direction=True) if value is not None else 'N/A'
            sections.append(f"| {label} | {formatted} |")
    
    # Volatility table
    volatility = price_metrics.get('volatility', {})
    if any(v is not None for v in volatility.values()):
        sections.append("### Volatility (Annualized)")
        sections.append("| Window | Volatility |")
        sections.append("|--------|------------|")
        
        for period, label in [('21D_annualized', '21 Day'), ('63D_annualized', '3 Month'), 
                             ('252D_annualized', '1 Year')]:
            value = volatility.get(period)
            formatted = format_percentage(value) if value is not None else 'N/A'
            sections.append(f"| {label} | {formatted} |")
    
    # Drawdown
    drawdown = price_metrics.get('drawdown', {})
    max_dd = drawdown.get('max_drawdown_pct')
    if max_dd is not None:
        sections.append("### Maximum Drawdown")
        dd_pct = format_percentage(abs(max_dd))
        sections.append(f"**Maximum Drawdown:** -{dd_pct}")
        
        peak_date = drawdown.get('peak_date')
        trough_date = drawdown.get('trough_date')
        recovery_date = drawdown.get('recovery_date')
        
        if peak_date and trough_date:
            sections.append(f"**Drawdown Period:** {peak_date} to {trough_date}")
            
            if recovery_date:
                sections.append(f"**Recovery Date:** {recovery_date}")
                recovery_days = drawdown.get('recovery_days', 0)
                sections.append(f"**Recovery Time:** {recovery_days} trading days")
            else:
                sections.append("**Recovery Status:** Not yet recovered")
    
    return '\n\n'.join(sections)


def _render_institutional_metrics(institutional_metrics: Optional[dict]) -> str:
    """Render institutional holdings section."""
    if not institutional_metrics:
        return "## Institutional Holdings\n\n*No institutional holdings data available.*"
    
    sections = ["## Institutional Holdings"]
    
    # Summary stats
    total_value = institutional_metrics.get('total_13f_value_usd', 0)
    total_holders = institutional_metrics.get('total_13f_holders', 0)
    quarter_end = institutional_metrics.get('quarter_end', 'Unknown')
    
    sections.append(f"**Total 13F Value:** {format_currency(total_value)}")
    sections.append(f"**Number of Holders:** {total_holders}")
    sections.append(f"**Reporting Quarter:** {quarter_end}")
    
    # Concentration metrics
    concentration = institutional_metrics.get('concentration', {})
    if concentration:
        sections.append("### Concentration Analysis")
        sections.append("| Metric | Value | Interpretation |")
        sections.append("|--------|-------|----------------|")
        
        cr1 = concentration.get('cr1')
        cr5 = concentration.get('cr5') 
        cr10 = concentration.get('cr10')
        hhi = concentration.get('hhi')
        
        if cr1 is not None:
            sections.append(f"| Top 1 Holder | {format_percentage(cr1)} | {_interpret_concentration(cr1)} |")
        if cr5 is not None:
            sections.append(f"| Top 5 Holders | {format_percentage(cr5)} | {_interpret_concentration(cr5)} |")
        if cr10 is not None:
            sections.append(f"| Top 10 Holders | {format_percentage(cr10)} | {_interpret_concentration(cr10)} |")
        if hhi is not None:
            sections.append(f"| HHI Index | {hhi:.4f} | {_interpret_hhi(hhi)} |")
    
    # Top holders table
    top_holders = institutional_metrics.get('top_holders', [])
    if top_holders:
        sections.append("### Top Institutional Holders")
        sections.append("| Rank | Institution | Value | % of 13F Total |")
        sections.append("|------|-------------|-------|----------------|")
        
        for holder in top_holders[:10]:  # Top 10
            rank = holder.get('rank', '?')
            filer = holder.get('filer', 'Unknown')[:40]  # Truncate long names
            value = format_currency(holder.get('value_usd'))
            pct = format_percentage(holder.get('pct_of_13f_total'))
            sections.append(f"| {rank} | {filer} | {value} | {pct} |")
    
    return '\n\n'.join(sections)


def _render_data_quality(data_quality: dict) -> str:
    """Render data quality section."""
    sections = ["## Data Quality"]
    
    # Price data quality
    price_coverage = data_quality.get('price_coverage_pct')
    missing_days = data_quality.get('missing_price_days', 0)
    
    if price_coverage is not None:
        sections.append(f"**Price Data Coverage:** {price_coverage:.1f}%")
        if missing_days > 0:
            sections.append(f"**Missing Price Days:** {missing_days}")
    
    # 13F data quality
    latest_13f = data_quality.get('latest_13f_quarter')
    age_days = data_quality.get('13f_data_age_days')
    
    if latest_13f:
        sections.append(f"**Latest 13F Quarter:** {latest_13f}")
        if age_days is not None:
            sections.append(f"**13F Data Age:** {age_days} days")
    else:
        sections.append("**13F Data:** Not available")
    
    return '\n\n'.join(sections)


def _render_footer(metadata: dict) -> str:
    """Render report footer with metadata."""
    calc_time = metadata.get('calculated_at', 'Unknown')
    version = metadata.get('calculation_version', '1.0.0')
    sources = metadata.get('data_sources', [])
    
    sources_str = ', '.join(sources) if sources else 'Unknown'
    
    return f"""---

## Report Metadata

**Calculation Time:** {calc_time}  
**Engine Version:** {version}  
**Data Sources:** {sources_str}

*This report is for informational purposes only. Not investment advice.*"""


# Helper functions
def format_percentage(value: Optional[float], show_direction: bool = False) -> str:
    """Format decimal as percentage with optional direction indicator."""
    if value is None:
        return 'N/A'
    
    pct = value * 100
    
    if show_direction:
        if pct > 0:
            return f"📈 +{pct:.2f}%"
        elif pct < 0:
            return f"{pct:.2f}%"
        else:
            return f"➡️ {pct:.2f}%"
    else:
        return f"{pct:.2f}%"


def format_currency(value: Optional[float]) -> str:
    """Format currency with appropriate scale (B/M/K)."""
    if value is None:
        return 'N/A'
    
    if value == 0:
        return '$0'
    
    abs_value = abs(value)
    
    if abs_value >= 1e9:
        return f"${value/1e9:.2f}B"
    elif abs_value >= 1e6:
        return f"${value/1e6:.2f}M"
    elif abs_value >= 1e3:
        return f"${value:,.0f}"
    else:
        return f"${value:.2f}"


def format_date_range(start: Optional[str], end: Optional[str], days: int) -> str:
    """Format date range with trading days count."""
    if not start or not end:
        return 'Not available'
    
    return f"{start} to {end} ({days} trading days)"


def _interpret_concentration(ratio: float) -> str:
    """Provide interpretation of concentration ratio."""
    if ratio < 0.1:
        return "Low concentration"
    elif ratio < 0.3:
        return "Moderate concentration" 
    elif ratio < 0.5:
        return "High concentration"
    else:
        return "Very high concentration"


def _interpret_hhi(hhi: float) -> str:
    """Provide interpretation of HHI value."""
    if hhi < 0.15:
        return "Competitive"
    elif hhi < 0.25:
        return "Moderately concentrated"
    else:
        return "Highly concentrated"
