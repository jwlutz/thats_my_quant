"""
13F concentration calculation utilities.
Pure functions for institutional ownership concentration metrics.
"""

from typing import Dict, Union


class ConcentrationError(Exception):
    """Raised when concentration calculation fails."""
    pass


def concentration_ratios(value_by_holder: Dict[str, float]) -> Dict[str, float]:
    """
    Calculate concentration ratios (CR1, CR5, CR10).
    
    Concentration ratio CRn = sum of top n holders / total value
    
    Args:
        value_by_holder: Dictionary mapping holder names to position values
        
    Returns:
        Dictionary with cr1, cr5, cr10 as decimals (0.45 = 45%)
        
    Raises:
        ConcentrationError: If invalid data
    """
    if not value_by_holder:
        raise ConcentrationError("No holders provided")
    
    # Check for non-positive values
    if any(value <= 0 for value in value_by_holder.values()):
        raise ConcentrationError("Non-positive values not allowed")
    
    # Sort holders by value (descending)
    sorted_holders = sorted(value_by_holder.items(), key=lambda x: x[1], reverse=True)
    total_value = sum(value_by_holder.values())
    
    # Calculate concentration ratios
    def cr_n(n: int) -> float:
        top_n_value = sum(value for _, value in sorted_holders[:n])
        return top_n_value / total_value
    
    return {
        'cr1': cr_n(1),
        'cr5': cr_n(5), 
        'cr10': cr_n(10)
    }


def herfindahl_index(value_by_holder: Dict[str, float]) -> float:
    """
    Calculate Herfindahl-Hirschman Index (HHI).
    
    HHI = Σ(share_i²) where share_i is the market share of holder i
    
    Args:
        value_by_holder: Dictionary mapping holder names to position values
        
    Returns:
        HHI as decimal (0 = perfect competition, 1 = monopoly)
        
    Raises:
        ConcentrationError: If invalid data
    """
    if not value_by_holder:
        raise ConcentrationError("No holders provided")
    
    if any(value <= 0 for value in value_by_holder.values()):
        raise ConcentrationError("Non-positive values not allowed")
    
    total_value = sum(value_by_holder.values())
    
    # Calculate sum of squared market shares
    hhi = 0.0
    for value in value_by_holder.values():
        share = value / total_value
        hhi += share ** 2
    
    return hhi


def calculate_concentration_metrics(
    value_by_holder: Dict[str, float]
) -> Dict[str, Union[float, int, None]]:
    """
    Calculate complete concentration metrics with error handling.
    
    Args:
        value_by_holder: Dictionary mapping holder names to position values
        
    Returns:
        Dictionary with all concentration metrics (or None if insufficient data)
    """
    if not value_by_holder or all(v <= 0 for v in value_by_holder.values()):
        return {
            'cr1': None,
            'cr5': None,
            'cr10': None,
            'hhi': None,
            'total_value': 0.0,
            'num_holders': 0,
            'top_holder_name': None,
            'top_holder_pct': None
        }
    
    try:
        # Calculate core metrics
        cr_metrics = concentration_ratios(value_by_holder)
        hhi = herfindahl_index(value_by_holder)
        
        # Additional metadata
        total_value = sum(value_by_holder.values())
        num_holders = len(value_by_holder)
        
        # Find top holder
        top_holder = max(value_by_holder.items(), key=lambda x: x[1])
        top_holder_name = top_holder[0]
        top_holder_pct = top_holder[1] / total_value
        
        return {
            'cr1': cr_metrics['cr1'],
            'cr5': cr_metrics['cr5'],
            'cr10': cr_metrics['cr10'],
            'hhi': hhi,
            'total_value': total_value,
            'num_holders': num_holders,
            'top_holder_name': top_holder_name,
            'top_holder_pct': top_holder_pct
        }
        
    except ConcentrationError:
        # Return null metrics if calculation fails
        return {
            'cr1': None,
            'cr5': None,
            'cr10': None,
            'hhi': None,
            'total_value': 0.0,
            'num_holders': 0,
            'top_holder_name': None,
            'top_holder_pct': None
        }


def analyze_13f_holdings(holdings_list: list) -> Dict[str, Union[float, int, None]]:
    """
    Analyze 13F holdings data for a specific ticker.
    
    Args:
        holdings_list: List of 13F holding dictionaries for a ticker
        
    Returns:
        Concentration metrics for the ticker's institutional ownership
    """
    if not holdings_list:
        return calculate_concentration_metrics({})
    
    # Aggregate by filer (institution)
    value_by_filer = {}
    for holding in holdings_list:
        filer = holding.get('filer', 'Unknown')
        value = holding.get('value_usd', 0.0)
        
        if filer in value_by_filer:
            value_by_filer[filer] += value
        else:
            value_by_filer[filer] = value
    
    return calculate_concentration_metrics(value_by_filer)


def concentration_interpretation(hhi: float) -> str:
    """
    Provide interpretation of HHI value.
    
    Args:
        hhi: Herfindahl-Hirschman Index value
        
    Returns:
        String interpretation of concentration level
    """
    if hhi is None:
        return "No data"
    elif hhi < 0.15:
        return "Low concentration (competitive)"
    elif hhi < 0.25:
        return "Moderate concentration"
    else:
        return "High concentration"
