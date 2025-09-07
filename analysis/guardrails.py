"""
Guardrails for analysis engine - validation and safety checks.
Implements Stop-and-Ask triggers for data quality issues.
"""

import pandas as pd
import numpy as np
from datetime import date, timedelta
from typing import Dict, Any, List, Optional, Tuple


class DataQualityError(Exception):
    """Raised when data quality issues require user intervention."""
    pass


class DataQualityWarning(UserWarning):
    """Raised when data quality issues should be noted but don't block execution."""
    pass


def validate_sufficient_data_for_metrics(
    price_df: pd.DataFrame,
    requested_windows: List[str]
) -> Tuple[List[str], List[str]]:
    """
    Validate sufficient data for requested metrics windows.
    
    Args:
        price_df: DataFrame with price data
        requested_windows: List of window names (e.g., ['1Y', '6M'])
        
    Returns:
        Tuple of (available_windows, insufficient_windows)
        
    Raises:
        DataQualityError: If critical windows lack sufficient data
    """
    if price_df.empty:
        raise DataQualityError("No price data available for analysis")
    
    trading_days = len(price_df)
    
    # Minimum trading days required for each window
    min_days_required = {
        '1D': 2,
        '1W': 6,     # 5 + 1
        '1M': 22,    # 21 + 1
        '3M': 64,    # 63 + 1
        '6M': 127,   # 126 + 1
        '1Y': 253    # 252 + 1
    }
    
    available_windows = []
    insufficient_windows = []
    
    for window in requested_windows:
        required = min_days_required.get(window, 0)
        if trading_days >= required:
            available_windows.append(window)
        else:
            insufficient_windows.append(window)
    
    # Critical check: If requesting 1Y but have < 150 days, stop and ask
    if '1Y' in requested_windows and trading_days < 150:
        raise DataQualityError(
            f"Insufficient data for 1Y analysis: have {trading_days} trading days, "
            f"need at least 150 for meaningful annual metrics. "
            f"Consider using shorter windows or gathering more historical data."
        )
    
    # Warning: If requesting 6M but have < 90 days
    if '6M' in requested_windows and trading_days < 90:
        import warnings
        warnings.warn(
            f"Limited data for 6M analysis: have {trading_days} trading days, "
            f"recommend at least 90 for reliable metrics.",
            DataQualityWarning
        )
    
    return available_windows, insufficient_windows


def detect_conflicting_13f_rows(holdings_df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Detect conflicting duplicate 13F rows that could skew analysis.
    
    Args:
        holdings_df: DataFrame with 13F holdings
        
    Returns:
        List of conflict descriptions
        
    Raises:
        DataQualityError: If conflicts require user intervention
    """
    conflicts = []
    
    if holdings_df.empty:
        return conflicts
    
    # Group by primary key (cik, cusip, as_of)
    pk_groups = holdings_df.groupby(['cik', 'cusip', 'as_of'])
    
    for (cik, cusip, as_of), group in pk_groups:
        if len(group) > 1:
            # Multiple rows with same primary key
            values = group['value_usd'].tolist()
            shares = group['shares'].tolist()
            
            # Check if values are significantly different
            if len(set(values)) > 1:  # Different values
                value_range = max(values) - min(values)
                avg_value = sum(values) / len(values)
                
                if value_range / avg_value > 0.1:  # >10% difference
                    conflict = {
                        'type': 'value_conflict',
                        'cik': cik,
                        'cusip': cusip,
                        'as_of': as_of,
                        'values': values,
                        'variance_pct': (value_range / avg_value) * 100
                    }
                    conflicts.append(conflict)
    
    # Critical: If >5% of holdings have conflicts, stop and ask
    if holdings_df.shape[0] > 0:
        conflict_rate = len(conflicts) / holdings_df.shape[0]
        if conflict_rate > 0.05:
            raise DataQualityError(
                f"High conflict rate in 13F data: {conflict_rate:.1%} of holdings have conflicts. "
                f"This may indicate data quality issues that need manual review. "
                f"Conflicts found: {len(conflicts)}"
            )
    
    return conflicts


def validate_numeric_inputs(metrics_dict: Dict[str, Any]) -> None:
    """
    Validate that all numeric metrics are finite and reasonable.
    
    Args:
        metrics_dict: Complete MetricsJSON dictionary
        
    Raises:
        DataQualityError: If NaN or infinite values found
    """
    def check_value(value, path: str):
        if value is None:
            return  # None is acceptable for missing data
        
        if isinstance(value, (int, float)):
            if np.isnan(value):
                raise DataQualityError(f"NaN value found in {path}")
            if np.isinf(value):
                raise DataQualityError(f"Infinite value found in {path}")
            
            # Reasonable bounds checks
            if path.endswith('_pct') or 'return' in path.lower():
                if abs(value) > 10.0:  # >1000% return/drawdown seems unrealistic
                    raise DataQualityError(f"Unrealistic percentage in {path}: {value}")
    
    # Check price metrics
    pm = metrics_dict.get('price_metrics', {})
    
    # Check returns
    returns = pm.get('returns', {})
    for window, value in returns.items():
        check_value(value, f'returns.{window}')
    
    # Check volatility
    volatility = pm.get('volatility', {})
    for window, value in volatility.items():
        check_value(value, f'volatility.{window}')
    
    # Check drawdown
    drawdown = pm.get('drawdown', {})
    check_value(drawdown.get('max_drawdown_pct'), 'drawdown.max_drawdown_pct')
    
    # Check institutional metrics
    im = metrics_dict.get('institutional_metrics')
    if im:
        concentration = im.get('concentration', {})
        for metric, value in concentration.items():
            check_value(value, f'concentration.{metric}')
            
            # Concentration ratios should be 0-1
            if value is not None and not (0 <= value <= 1):
                raise DataQualityError(f"Concentration ratio {metric} out of bounds: {value}")


def check_data_freshness(
    price_df: pd.DataFrame,
    holdings_df: Optional[pd.DataFrame],
    max_price_age_days: int = 7,
    max_13f_age_days: int = 120
) -> List[str]:
    """
    Check data freshness and warn about stale data.
    
    Args:
        price_df: Price data DataFrame
        holdings_df: Holdings data DataFrame (optional)
        max_price_age_days: Maximum acceptable age for price data
        max_13f_age_days: Maximum acceptable age for 13F data
        
    Returns:
        List of freshness warnings
    """
    warnings = []
    today = date.today()
    
    # Check price data freshness
    if not price_df.empty:
        latest_price_date = pd.to_datetime(price_df['date']).max().date()
        price_age = (today - latest_price_date).days
        
        if price_age > max_price_age_days:
            warnings.append(
                f"Price data is {price_age} days old (latest: {latest_price_date}). "
                f"Consider updating with recent data."
            )
    
    # Check 13F data freshness
    if holdings_df is not None and not holdings_df.empty:
        latest_13f_date = pd.to_datetime(holdings_df['as_of']).max().date()
        f13_age = (today - latest_13f_date).days
        
        if f13_age > max_13f_age_days:
            warnings.append(
                f"13F data is {f13_age} days old (latest quarter: {latest_13f_date}). "
                f"Quarterly filings may be available with more recent data."
            )
    
    return warnings


def validate_price_data_integrity(price_df: pd.DataFrame) -> List[str]:
    """
    Validate price data integrity and detect anomalies.
    
    Args:
        price_df: Price data DataFrame
        
    Returns:
        List of integrity warnings
    """
    warnings = []
    
    if price_df.empty:
        return warnings
    
    # Check for large price gaps (>20% daily moves)
    if len(price_df) > 1:
        closes = price_df['close'].tolist()
        for i in range(1, len(closes)):
            daily_change = abs((closes[i] / closes[i-1]) - 1)
            if daily_change > 0.20:  # >20% daily move
                date_str = price_df.iloc[i]['date']
                warnings.append(
                    f"Large price movement on {date_str}: "
                    f"{daily_change:.1%} change (${closes[i-1]:.2f} → ${closes[i]:.2f})"
                )
    
    # Check for zero volume days
    zero_volume_days = price_df[price_df['volume'] == 0]
    if not zero_volume_days.empty:
        dates = zero_volume_days['date'].tolist()
        warnings.append(f"Zero volume detected on {len(dates)} days: {dates}")
    
    # Check for price consistency (high >= low, etc.)
    invalid_prices = price_df[
        (price_df['high'] < price_df['low']) |
        (price_df['high'] < price_df['open']) |
        (price_df['high'] < price_df['close']) |
        (price_df['low'] > price_df['open']) |
        (price_df['low'] > price_df['close'])
    ]
    
    if not invalid_prices.empty:
        warnings.append(f"Price logic violations found on {len(invalid_prices)} days")
    
    return warnings


def run_all_guardrails(
    ticker: str,
    price_df: pd.DataFrame,
    holdings_df: Optional[pd.DataFrame],
    metrics_dict: Dict[str, Any],
    requested_windows: List[str] = ['1D', '1W', '1M', '3M', '6M', '1Y']
) -> Dict[str, Any]:
    """
    Run all guardrail checks and compile results.
    
    Args:
        ticker: Stock ticker
        price_df: Price data
        holdings_df: Holdings data (optional)
        metrics_dict: Calculated metrics
        requested_windows: Requested analysis windows
        
    Returns:
        Dictionary with guardrail results and recommendations
        
    Raises:
        DataQualityError: If critical issues found that require user intervention
    """
    guardrail_results = {
        'ticker': ticker,
        'timestamp': date.today().isoformat(),
        'data_quality_checks': {
            'sufficient_data': None,
            'conflicting_13f_rows': None,
            'numeric_validation': None,
            'freshness_check': None,
            'price_integrity': None
        },
        'warnings': [],
        'errors': [],
        'recommendations': []
    }
    
    try:
        # 1. Sufficient data check
        available, insufficient = validate_sufficient_data_for_metrics(price_df, requested_windows)
        guardrail_results['data_quality_checks']['sufficient_data'] = {
            'available_windows': available,
            'insufficient_windows': insufficient
        }
        
        if insufficient:
            guardrail_results['warnings'].append(
                f"Insufficient data for windows: {insufficient}. "
                f"Consider gathering more historical data."
            )
        
        # 2. 13F conflicts check
        conflicts = detect_conflicting_13f_rows(holdings_df) if holdings_df is not None else []
        guardrail_results['data_quality_checks']['conflicting_13f_rows'] = conflicts
        
        if conflicts:
            guardrail_results['warnings'].append(
                f"Found {len(conflicts)} conflicting 13F holdings. "
                f"Review data quality before making investment decisions."
            )
        
        # 3. Numeric validation
        validate_numeric_inputs(metrics_dict)
        guardrail_results['data_quality_checks']['numeric_validation'] = 'passed'
        
        # 4. Freshness check
        freshness_warnings = check_data_freshness(price_df, holdings_df)
        guardrail_results['data_quality_checks']['freshness_check'] = freshness_warnings
        guardrail_results['warnings'].extend(freshness_warnings)
        
        # 5. Price integrity check
        integrity_warnings = validate_price_data_integrity(price_df)
        guardrail_results['data_quality_checks']['price_integrity'] = integrity_warnings
        guardrail_results['warnings'].extend(integrity_warnings)
        
        # Generate recommendations
        guardrail_results['recommendations'] = _generate_recommendations(
            price_df, holdings_df, available, insufficient
        )
        
        return guardrail_results
        
    except DataQualityError as e:
        guardrail_results['errors'].append(str(e))
        raise  # Re-raise for caller to handle


def _generate_recommendations(
    price_df: pd.DataFrame,
    holdings_df: Optional[pd.DataFrame],
    available_windows: List[str],
    insufficient_windows: List[str]
) -> List[str]:
    """Generate actionable recommendations based on data analysis."""
    recommendations = []
    
    trading_days = len(price_df)
    
    # Data collection recommendations
    if trading_days < 63:
        recommendations.append(
            "Collect more historical price data (target: 3+ months) for better volatility analysis"
        )
    
    if trading_days < 252:
        recommendations.append(
            "Collect more historical price data (target: 1+ year) for annual metrics"
        )
    
    # 13F recommendations
    if holdings_df is None or holdings_df.empty:
        recommendations.append(
            "Collect 13F holdings data to analyze institutional ownership patterns"
        )
    elif len(holdings_df) < 5:
        recommendations.append(
            "Limited institutional data found. Consider checking if ticker has significant institutional ownership"
        )
    
    # Analysis recommendations
    if '1Y' not in available_windows:
        recommendations.append(
            "Focus on shorter-term metrics (1D, 1W, 1M) until more data is available"
        )
    
    if trading_days >= 252 and '1Y' in available_windows:
        recommendations.append(
            "Sufficient data for comprehensive analysis including annual volatility and drawdown metrics"
        )
    
    return recommendations


def create_data_quality_report(guardrail_results: Dict[str, Any]) -> str:
    """
    Create human-readable data quality report.
    
    Args:
        guardrail_results: Results from run_all_guardrails()
        
    Returns:
        Formatted text report
    """
    ticker = guardrail_results['ticker']
    timestamp = guardrail_results['timestamp']
    
    report = [
        f"📊 Data Quality Report for {ticker}",
        f"Generated: {timestamp}",
        "=" * 50,
        ""
    ]
    
    # Errors
    errors = guardrail_results.get('errors', [])
    if errors:
        report.append("🚨 CRITICAL ISSUES:")
        for error in errors:
            report.append(f"   • {error}")
        report.append("")
    
    # Warnings
    warnings = guardrail_results.get('warnings', [])
    if warnings:
        report.append("⚠️  WARNINGS:")
        for warning in warnings:
            report.append(f"   • {warning}")
        report.append("")
    
    # Data availability
    data_check = guardrail_results['data_quality_checks']['sufficient_data']
    if data_check:
        available = data_check['available_windows']
        insufficient = data_check['insufficient_windows']
        
        report.append("📈 METRIC AVAILABILITY:")
        if available:
            report.append(f"   ✅ Available: {', '.join(available)}")
        if insufficient:
            report.append(f"   ❌ Insufficient data: {', '.join(insufficient)}")
        report.append("")
    
    # Recommendations
    recommendations = guardrail_results.get('recommendations', [])
    if recommendations:
        report.append("💡 RECOMMENDATIONS:")
        for rec in recommendations:
            report.append(f"   • {rec}")
        report.append("")
    
    # Overall status
    if errors:
        report.append("🚨 OVERALL STATUS: CRITICAL ISSUES FOUND")
        report.append("   Manual review required before proceeding.")
    elif warnings:
        report.append("⚠️  OVERALL STATUS: WARNINGS PRESENT")
        report.append("   Proceed with caution and note limitations.")
    else:
        report.append("✅ OVERALL STATUS: DATA QUALITY ACCEPTABLE")
        report.append("   Safe to proceed with analysis.")
    
    return "\n".join(report)
