"""
Display formatters for Enhanced MetricsJSON v2.
Deterministic string formatting for percentages, currency, and dates.
"""

from datetime import datetime, date
from typing import Optional, Union


class FormatterError(Exception):
    """Raised when formatter input validation fails."""
    pass


def format_percentage(value: Optional[float], decimal_places: int = 1) -> str:
    """
    Format decimal as percentage with specified precision.
    
    Args:
        value: Decimal value (0.0845 = 8.45%)
        decimal_places: Number of decimal places (default: 1)
        
    Returns:
        Formatted percentage string (e.g., "8.5%")
    """
    if value is None:
        return "Not available"
    
    if not isinstance(value, (int, float)):
        raise FormatterError(f"Percentage value must be numeric, got {type(value)}")
    
    # Convert to percentage
    pct = value * 100
    
    # Format with specified decimal places
    if decimal_places == 0:
        return f"{pct:.0f}%"
    elif decimal_places == 1:
        return f"{pct:.1f}%"
    elif decimal_places == 2:
        return f"{pct:.2f}%"
    else:
        return f"{pct:.{decimal_places}f}%"


def format_currency(value: Optional[float], force_scale: Optional[str] = None) -> str:
    """
    Format currency with appropriate scale (B/M/K).
    
    Args:
        value: Dollar amount
        force_scale: Force specific scale ('B', 'M', 'K', None)
        
    Returns:
        Formatted currency string (e.g., "$12.3B", "$1,234")
    """
    if value is None:
        return "Not available"
    
    if not isinstance(value, (int, float)):
        raise FormatterError(f"Currency value must be numeric, got {type(value)}")
    
    if value == 0:
        return "$0"
    
    abs_value = abs(value)
    sign = "-" if value < 0 else ""
    
    # Apply forced scale if specified
    if force_scale == 'B':
        return f"{sign}${abs_value/1e9:.1f}B"
    elif force_scale == 'M':
        return f"{sign}${abs_value/1e6:.1f}M"
    elif force_scale == 'K':
        return f"{sign}${abs_value/1e3:.1f}K"
    
    # Auto-scale based on magnitude
    if abs_value >= 1e9:
        return f"{sign}${abs_value/1e9:.1f}B"
    elif abs_value >= 1e6:
        return f"{sign}${abs_value/1e6:.1f}M"
    elif abs_value >= 1e3:
        return f"{sign}${abs_value:,.0f}"
    else:
        return f"{sign}${abs_value:.2f}"


def format_date_display(date_input: Union[str, date, datetime]) -> str:
    """
    Format date as "Month D, YYYY".
    
    Args:
        date_input: Date as string, date object, or datetime object
        
    Returns:
        Formatted date string (e.g., "July 15, 2025")
    """
    if date_input is None:
        return "Not available"
    
    # Convert to date object
    if isinstance(date_input, str):
        try:
            if 'T' in date_input:
                # ISO datetime string
                dt = datetime.fromisoformat(date_input.replace('Z', '+00:00'))
                date_obj = dt.date()
            else:
                # ISO date string
                date_obj = date.fromisoformat(date_input)
        except ValueError:
            raise FormatterError(f"Invalid date string: {date_input}")
    elif isinstance(date_input, datetime):
        date_obj = date_input.date()
    elif isinstance(date_input, date):
        date_obj = date_input
    else:
        raise FormatterError(f"Date must be string, date, or datetime, got {type(date_input)}")
    
    # Format as "Month D, YYYY"
    return date_obj.strftime("%B %d, %Y")


def format_window_display(window_days: int, window_type: str = "day") -> str:
    """
    Format time window for display.
    
    Args:
        window_days: Number of days in window
        window_type: Type of window ("day", "trading_day")
        
    Returns:
        Formatted window string (e.g., "(21-day)", "(252-day)")
    """
    if window_days is None:
        return "Not available"
    
    if not isinstance(window_days, int) or window_days <= 0:
        raise FormatterError(f"Window days must be positive integer, got {window_days}")
    
    return f"({window_days}-day)"


def format_return_period(period_key: str) -> str:
    """
    Format return period key for display.
    
    Args:
        period_key: Period key (e.g., "1D", "1M", "1Y")
        
    Returns:
        Formatted period string (e.g., "1-day", "1-month", "1-year")
    """
    period_map = {
        '1D': '1-day',
        '1W': '1-week', 
        '1M': '1-month',
        '3M': '3-month',
        '6M': '6-month',
        '1Y': '1-year'
    }
    
    return period_map.get(period_key, period_key.lower())


def format_recovery_status(
    recovery_date: Optional[str],
    as_of_date: str
) -> str:
    """
    Format recovery status message.
    
    Args:
        recovery_date: Recovery date string or None
        as_of_date: Analysis as-of date
        
    Returns:
        Recovery status message
    """
    if recovery_date is None:
        as_of_display = format_date_display(as_of_date)
        return f"unrecovered as of {as_of_display}"
    else:
        recovery_display = format_date_display(recovery_date)
        return f"fully recovered by {recovery_display}"


def build_audit_index_entry(
    formatted_values: list,
    category: str
) -> list:
    """
    Build audit index entry for a category.
    
    Args:
        formatted_values: List of formatted values
        category: Category name for validation
        
    Returns:
        Deduplicated, sorted list of values
    """
    if not isinstance(formatted_values, list):
        raise FormatterError(f"Formatted values must be list, got {type(formatted_values)}")
    
    # Remove None values and deduplicate
    clean_values = []
    for value in formatted_values:
        if value is not None and value != "Not available":
            if isinstance(value, str):
                clean_values.append(value)
            else:
                clean_values.append(str(value))
    
    # Deduplicate and sort for consistency
    unique_values = sorted(list(set(clean_values)))
    
    return unique_values
