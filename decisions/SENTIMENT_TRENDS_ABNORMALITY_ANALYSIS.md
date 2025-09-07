# Sentiment Trends Abnormality Analysis - Executive Summary

**Date:** 2025-01-XX  
**Subject:** Individual trend scoring based on abnormality detection  
**Confidence Level:** 85% (need clarification on specific abnormality thresholds)

## Core Concept: Abnormality-Based Sentiment Scoring

### The Insight
**Absolute sentiment values are less meaningful than deviations from normal patterns.**

For example:
- **Google Trends**: AAPL having 50/100 search volume is normal, but spiking to 95/100 (90th percentile) signals unusual retail interest
- **Insider Trading**: 2-3 routine executive sales per month is normal, but 15 sales in one week signals concern
- **News Volume**: 5 articles/day is normal for AAPL, but 25 articles/day signals a catalyst event
- **13F Changes**: 2% quarterly turnover is normal, but 15% turnover signals institutional sentiment shift

### Proposed Abnormality Framework

#### **Statistical Approach**
```python
def calculate_abnormality_score(current_value: float, historical_baseline: dict) -> dict:
    """
    Calculate abnormality score using statistical deviation.
    
    Args:
        current_value: Current metric value
        historical_baseline: {'mean': float, 'std': float, 'percentiles': dict}
        
    Returns:
        {
            'abnormality_score': float (-3.0 to +3.0),  # Z-score capped
            'percentile': float (0.0 to 1.0),           # Where current value ranks
            'classification': str,                       # 'normal', 'unusual', 'extreme'
            'direction': str,                            # 'above_normal', 'below_normal', 'normal'
            'confidence': float (0.0 to 1.0)           # Based on sample size
        }
    """
```

#### **Abnormality Classifications**
- **Normal**: Within 1 standard deviation (68% of historical data)
- **Unusual**: 1-2 standard deviations (27% of historical data) 
- **Extreme**: >2 standard deviations (5% of historical data)

#### **Sentiment Mapping**
- **Positive Abnormality**: Above-normal buying, search interest, positive news volume
- **Negative Abnormality**: Above-normal selling, negative news volume, search spikes during bad news
- **Direction Matters**: High search volume during earnings = positive, during scandal = negative

## Specific Implementation Questions

### 1. Baseline Calculation Periods
**Question**: What historical periods should we use for each source?

**Proposed Approach**:
- **Google Trends**: 90-day rolling baseline (sufficient for seasonal patterns)
- **Insider Trading**: 365-day baseline (captures annual patterns, executive schedules)
- **News Volume**: 30-day baseline (news cycles are shorter)
- **13F Changes**: 8-quarter baseline (2-year institutional pattern)

**Trade-off**: Longer baselines = more stable but less responsive to regime changes

### 2. Abnormality Thresholds
**Question**: What Z-score thresholds define unusual vs extreme activity?

**Proposed Thresholds**:
```python
ABNORMALITY_THRESHOLDS = {
    'normal': (-1.0, +1.0),      # 68% of data
    'unusual': (-2.0, +2.0),     # 95% of data  
    'extreme': (-3.0, +3.0),     # 99.7% of data
    'cap_at': 3.0                # Cap extreme outliers
}
```

**Alternative**: Use percentile-based thresholds (more robust to outliers)?

### 3. Context-Aware Scoring
**Question**: Should abnormality scoring consider market context?

**Examples**:
- High search volume during earnings week = less abnormal than during quiet periods
- Insider selling before dividend ex-date = normal vs random selling = abnormal
- News volume spike during sector rotation = less significant than company-specific spike

**Proposed Solution**: Context flags in abnormality calculation
```python
def calculate_abnormality_score(
    current_value: float, 
    historical_baseline: dict,
    context_flags: dict = None  # {'earnings_week': bool, 'dividend_ex': bool, 'sector_event': bool}
) -> dict:
```

### 4. Multi-Timeframe Analysis
**Question**: Should we score abnormality across multiple timeframes?

**Proposed Timeframes**:
- **Short-term**: 7-day window (immediate sentiment shifts)
- **Medium-term**: 30-day window (trend development)
- **Long-term**: 90-day window (structural changes)

**Composite Abnormality**: Weight recent timeframes more heavily
- 7-day: 50% weight
- 30-day: 30% weight  
- 90-day: 20% weight

### 5. Data Quality Requirements
**Question**: What minimum data requirements ensure reliable abnormality detection?

**Proposed Minimums**:
- **Google Trends**: 30 days of historical data
- **Insider Trading**: 90 days of transactions (may be sparse)
- **News**: 30 days of articles
- **13F**: 2 quarters minimum

**Fallback**: If insufficient data, flag as "insufficient_baseline" and use simple scoring

## Implementation Complexity Assessment

### **Low Complexity** ✅
- **Z-score calculation**: Standard statistical approach
- **Percentile ranking**: Well-established algorithms
- **Rolling baselines**: Simple SQL window functions

### **Medium Complexity** ⚠️
- **Context-aware scoring**: Requires market calendar integration
- **Multi-timeframe weighting**: More complex aggregation logic
- **Dynamic threshold adjustment**: Adapts to changing market regimes

### **High Complexity** 🔴
- **Regime change detection**: Identifying when baselines should reset
- **Cross-asset correlation**: Adjusting for sector/market-wide events
- **Predictive modeling**: Using abnormality to predict price movements

## Recommended Approach

### **Phase 1: Simple Abnormality (Implement First)**
1. **Single timeframe** (7-day window)
2. **Fixed baselines** (90-day historical)
3. **Simple Z-score** calculation with caps
4. **No context awareness** initially

### **Phase 2: Enhanced Abnormality (Future)**
1. **Multi-timeframe** scoring
2. **Context-aware** adjustments
3. **Dynamic threshold** adaptation

## Technical Questions for Clarification

### **1. Baseline Storage Strategy**
Should we:
- **A**: Pre-calculate and store rolling baselines in database?
- **B**: Calculate baselines on-demand from raw data?
- **C**: Hybrid approach (cache recent baselines, calculate on-demand for older periods)?

**Recommendation**: Option A for performance, with periodic recalculation

### **2. Abnormality Aggregation**
How should we combine abnormality scores from different sources?
- **A**: Simple weighted average of Z-scores
- **B**: Percentile-based ranking then average
- **C**: Non-linear combination (extreme abnormalities get amplified)

**Recommendation**: Option A for simplicity and interpretability

### **3. Missing Data Handling**
When a source has insufficient baseline data:
- **A**: Exclude from composite score calculation
- **B**: Use simplified scoring (e.g., above/below median)
- **C**: Flag as "low_confidence" but include

**Recommendation**: Option C with clear confidence indicators

## Expected Benefits

### **Signal Quality Improvements**
- **Higher Precision**: Abnormal patterns more predictive than absolute values
- **Context Sensitivity**: Same event scored differently based on historical patterns
- **Early Warning**: Detect unusual activity before it becomes widely recognized

### **User Experience**
- **Interpretable**: "Search interest is 2.5 standard deviations above normal"
- **Actionable**: "Insider selling is at 95th percentile of historical activity"
- **Confidence-Weighted**: Clear indicators when data is insufficient

## Risk Assessment

### **Low Risk** ✅
- **Statistical Foundation**: Z-scores and percentiles are well-established
- **Incremental Enhancement**: Can implement on top of existing architecture
- **Graceful Degradation**: Falls back to simple scoring when baselines insufficient

### **Medium Risk** ⚠️
- **Baseline Quality**: Historical data quality affects abnormality detection accuracy
- **Parameter Tuning**: Threshold selection requires empirical validation
- **Computational Load**: Rolling baseline calculations may impact performance

## Recommendation

**PROCEED with abnormality-based scoring using the Phase 1 approach:**

1. **Implement simple abnormality scoring** for each source individually
2. **Use 90-day rolling baselines** with Z-score calculation
3. **Start with fixed thresholds** (normal/unusual/extreme at 1σ/2σ/3σ)
4. **Add context awareness** in future iterations

This approach provides **significantly better sentiment signals** while maintaining our local-first, deterministic principles.

---

**Questions for User Clarification:**
1. Do you prefer Z-score or percentile-based abnormality scoring?
2. Should we implement multi-timeframe analysis immediately or start simple?
3. Any specific abnormality thresholds you'd prefer?
4. Should abnormality scoring be ticker-specific or use market-wide baselines?
