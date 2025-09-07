"""
Classification labelers for Enhanced MetricsJSON v2.
Deterministic threshold-based classifications for volatility and concentration.
"""

from typing import Dict, Any, Optional


class LabelerError(Exception):
    """Raised when labeler input validation fails."""
    pass


def classify_vol_level(ann_vol: float) -> str:
    """
    Classify annualized volatility level.
    
    Thresholds:
    - Low: < 20%
    - Moderate: 20% - 35%
    - High: > 35%
    
    Args:
        ann_vol: Annualized volatility as decimal (0.25 = 25%)
        
    Returns:
        Classification level: "low", "moderate", or "high"
        
    Raises:
        LabelerError: If input is invalid
    """
    if ann_vol is None:
        raise LabelerError("Volatility cannot be None")
    
    if ann_vol < 0:
        raise LabelerError("Volatility must be non-negative")
    
    if ann_vol > 5.0:  # 500% volatility seems unrealistic
        raise LabelerError(f"Unrealistic volatility: {ann_vol}")
    
    # Apply thresholds
    if ann_vol < 0.20:      # < 20%
        return "low"
    elif ann_vol <= 0.35:   # 20% - 35%
        return "moderate"
    else:                   # > 35%
        return "high"


def classify_concentration(concentration_data: Dict[str, Any]) -> Dict[str, str]:
    """
    Classify institutional concentration level.
    
    Prefers CR5, falls back to HHI if CR5 not available.
    
    CR5 Thresholds:
    - Low: < 25%
    - Moderate: 25% - 40%
    - High: > 40%
    
    HHI Thresholds:
    - Low: < 0.10
    - Moderate: 0.10 - 0.18
    - High: > 0.18
    
    Args:
        concentration_data: Dictionary with cr5 and/or hhi values
        
    Returns:
        Dictionary with level and basis: {"level": "moderate", "basis": "CR5"}
    """
    # Prefer CR5 when available
    if 'cr5' in concentration_data and concentration_data['cr5'] is not None:
        cr5 = concentration_data['cr5']
        
        # Validate CR5 range
        if cr5 < 0 or cr5 > 1:
            raise LabelerError(f"CR5 must be between 0 and 1, got {cr5}")
        
        # Apply CR5 thresholds
        if cr5 < 0.25:
            level = "low"
        elif cr5 <= 0.40:
            level = "moderate"
        else:
            level = "high"
        
        return {"level": level, "basis": "CR5"}
    
    # Fallback to HHI
    elif 'hhi' in concentration_data and concentration_data['hhi'] is not None:
        hhi = concentration_data['hhi']
        
        # Validate HHI range
        if hhi < 0 or hhi > 1:
            raise LabelerError(f"HHI must be between 0 and 1, got {hhi}")
        
        # Apply HHI thresholds
        if hhi < 0.10:
            level = "low"
        elif hhi <= 0.18:
            level = "moderate"
        else:
            level = "high"
        
        return {"level": level, "basis": "HHI"}
    
    # No usable concentration data
    else:
        return {"level": "unknown", "basis": "insufficient_data"}


def classify_drawdown_severity(max_drawdown_pct: float) -> str:
    """
    Classify drawdown severity level.
    
    Thresholds:
    - Minor: > -10%
    - Moderate: -10% to -25%
    - Severe: < -25%
    
    Args:
        max_drawdown_pct: Maximum drawdown as negative decimal (-0.15 = -15%)
        
    Returns:
        Severity level: "minor", "moderate", or "severe"
    """
    if max_drawdown_pct is None:
        return "unknown"
    
    if max_drawdown_pct > 0:
        raise LabelerError("Drawdown should be negative or zero")
    
    # Convert to positive percentage for comparison
    dd_pct = abs(max_drawdown_pct)
    
    if dd_pct < 0.10:       # < 10%
        return "minor"
    elif dd_pct <= 0.25:    # 10% - 25%
        return "moderate"
    else:                   # > 25%
        return "severe"


def classify_return_performance(returns_data: Dict[str, Optional[float]]) -> Dict[str, str]:
    """
    Classify return performance across periods.
    
    Args:
        returns_data: Dictionary of returns by period
        
    Returns:
        Dictionary with performance classification
    """
    if not returns_data:
        return {"overall": "unknown", "trend": "unknown"}
    
    # Filter out None values
    valid_returns = {k: v for k, v in returns_data.items() if v is not None}
    
    if not valid_returns:
        return {"overall": "unknown", "trend": "unknown"}
    
    # Classify overall performance (use longest available period)
    periods_order = ['1Y', '6M', '3M', '1M', '1W', '1D']
    best_return = None
    best_period = None
    
    for period in periods_order:
        if period in valid_returns:
            best_return = valid_returns[period]
            best_period = period
            break
    
    if best_return is None:
        return {"overall": "unknown", "trend": "unknown"}
    
    # Classify performance level
    if best_return > 0.20:      # > 20%
        overall = "strong"
    elif best_return > 0.05:    # 5% - 20%
        overall = "positive"
    elif best_return > -0.05:   # -5% to 5%
        overall = "flat"
    elif best_return > -0.20:   # -20% to -5%
        overall = "negative"
    else:                       # < -20%
        overall = "poor"
    
    # Determine trend (compare short vs long term if available)
    trend = "unknown"
    if '1M' in valid_returns and '1Y' in valid_returns:
        monthly = valid_returns['1M']
        yearly = valid_returns['1Y']
        
        if monthly > yearly * 0.5:  # Monthly momentum > half of yearly
            trend = "accelerating"
        elif monthly < yearly * 0.1:  # Monthly much weaker
            trend = "decelerating"
        else:
            trend = "consistent"
    
    return {
        "overall": overall,
        "trend": trend,
        "best_period": best_period,
        "best_return": best_return
    }
