# Enhanced Sentiment Architecture - Executive Summary

**Date:** 2025-01-XX  
**Subject:** Multi-Timeframe Abnormality-Based Sentiment Analysis with Context Awareness  
**Status:** Architecture Defined - Ready for Implementation  
**Confidence Level:** 95%

## Executive Summary

We are enhancing the sentiment analysis system to use **abnormality-based scoring across multiple timeframes** with **context-aware adjustments** and **public sentiment as core functionality**. This creates a sophisticated early-warning system that detects unusual market behavior patterns rather than just measuring absolute sentiment levels.

## Core Innovation: Abnormality Detection

### **The Insight**
**Deviations from normal patterns are more predictive than absolute values.**

**Examples**:
- **Google Trends**: AAPL search volume jumping from normal 40/100 to 95/100 = retail FOMO signal
- **Insider Trading**: 15 executive sales in one week (vs normal 2-3/month) = insider concern
- **Reddit**: 500 mentions/day (vs normal 50/day) = viral discussion catalyst
- **News Volume**: 25 articles/day (vs normal 5/day) = breaking news event

### **Multi-Timeframe Analysis**
Score abnormality across **3 timeframes** with weighted importance:
- **7-day window (50% weight)**: Immediate sentiment shifts and catalysts
- **30-day window (30% weight)**: Trend development and momentum
- **90-day window (20% weight)**: Structural sentiment changes

## Enhanced Data Architecture

### **5 Core Data Sources (Equal 20% Weight Each)**
1. **Institutional Sentiment**: 13F deltas + concentration changes
2. **Insider Sentiment**: SEC Form 4 transaction abnormality
3. **News Sentiment**: Article volume + FinBERT sentiment abnormality  
4. **Search Sentiment**: Google Trends volume spike abnormality
5. **Public Sentiment**: Reddit/X mention volume + sentiment abnormality

### **Context Awareness Integration**
**Automatic adjustments** for known market events:
- **Earnings Week**: Higher news/search volume expected (adjust thresholds +20%)
- **Dividend Ex-Date**: Higher insider selling expected (adjust thresholds +15%)
- **Earnings Call**: Higher public discussion expected (adjust thresholds +25%)
- **Sector Events**: Cross-ticker correlation adjustments

### **Statistical Framework**
```python
# For each source and timeframe:
abnormality_score = min(3.0, max(-3.0, (current_value - baseline_mean) / baseline_std))
percentile = scipy.stats.percentileofscore(historical_data, current_value) / 100.0

classification = {
    'normal': abs(abnormality_score) <= 1.0,      # 68% of historical data
    'unusual': 1.0 < abs(abnormality_score) <= 2.0,  # 27% of historical data
    'extreme': abs(abnormality_score) > 2.0       # 5% of historical data
}
```

## Implementation Plan

### **Enhanced Phase SNT Structure**

#### **SNT1: Core Data Ingestion** ✅
- [x] RSS news ingestion with deduplication
- [ ] Google Trends integration (pytrends)
- [ ] Insider trading integration (SEC Form 4)
- [ ] Public sentiment integration (Reddit/X APIs)

#### **SNT2: Baseline Management**
- [ ] Rolling baseline calculation for all metrics
- [ ] Abnormality detection engine (Z-scores + percentiles)
- [ ] Context event detection and calendar integration
- [ ] Baseline storage and update mechanisms

#### **SNT3: Context Awareness**
- [ ] Earnings calendar integration
- [ ] Dividend schedule tracking
- [ ] Earnings call transcript detection
- [ ] Sector event correlation analysis

#### **SNT4: Abnormality Scoring Engine**
- [ ] Multi-timeframe abnormality calculation
- [ ] Context-aware threshold adjustments
- [ ] Catalyst detection and classification
- [ ] Composite abnormality aggregation

#### **SNT5: Integration & Reports**
- [ ] Enhanced MetricsJSON v2 integration
- [ ] LangChain narrative generation for abnormality insights
- [ ] CLI commands for sentiment analysis
- [ ] Performance optimization and caching

## Technical Architecture

### **New Database Tables** (5 additional):
1. `public_sentiment`: Reddit/X posts with sentiment scores
2. `context_events`: Earnings, dividends, calls, sector events
3. `abnormality_baselines`: Rolling statistical baselines per metric
4. `google_trends`: Search interest time series
5. Enhanced `sentiment_snapshot`: Multi-timeframe abnormality scores

### **Key Dependencies**:
- `pytrends`: Google Trends access
- `praw`: Reddit API (core functionality)
- `tweepy`: X (Twitter) API v2 (core functionality)
- `scipy`: Statistical functions for abnormality calculation
- `pandas-market-calendars`: Market calendar for context awareness

### **Context Integration Sources**:
- **Earnings Calendar**: yfinance earnings dates
- **Dividend Calendar**: yfinance dividend schedules  
- **Earnings Calls**: SEC 8-K filings + transcript detection
- **Sector Events**: Cross-ticker correlation analysis

## Expected Signal Quality

### **Dramatic Improvement in Predictive Power**
- **Before**: Basic sentiment averages (lagging indicators)
- **After**: Multi-timeframe abnormality detection (leading indicators)

### **Example Abnormality Signals**
```
AAPL Sentiment Analysis - January 15, 2025

Composite Abnormality: +2.1σ (95th percentile) - UNUSUAL
Classification: Above-normal positive sentiment

Components:
- Institutional: +0.5σ (normal) - Typical 13F activity
- Insider: -1.8σ (unusual) - Above-normal selling
- News: +2.8σ (extreme) - Major positive news spike  
- Search: +2.5σ (extreme) - Viral search interest
- Public: +1.2σ (unusual) - High Reddit/X engagement

Timeframes:
- 7-day: +2.3σ (extreme) - Recent catalyst event
- 30-day: +1.1σ (unusual) - Building momentum
- 90-day: +0.8σ (normal) - Within structural range

Context: Earnings week (+20% threshold adjustment)
```

## Risk Assessment

### **Low Risk** ✅
- **Proven Statistical Methods**: Z-scores and percentiles are well-established
- **Incremental Enhancement**: Builds on existing RSS foundation
- **Graceful Degradation**: Falls back to simple scoring when data insufficient

### **Medium Risk** ⚠️
- **API Dependencies**: Reddit/X APIs require credentials and have rate limits
- **Computational Complexity**: Multi-timeframe analysis increases processing load
- **Context Detection**: Earnings/dividend calendar accuracy affects adjustments

### **Mitigation Strategies**
- **API Fallback**: System works without public sentiment if APIs unavailable
- **Caching Strategy**: Aggressive baseline caching to reduce computation
- **Manual Override**: Allow manual context event entry if auto-detection fails

## Resource Requirements

### **Additional Storage**: ~50MB per ticker per year
- Abnormality baselines: ~1MB per ticker
- Public sentiment: ~20MB per ticker (high-volume tickers)
- Context events: ~1MB per ticker
- Google Trends: ~5MB per ticker

### **Processing Power**: 
- **Baseline Calculation**: ~5 seconds per ticker per day
- **Abnormality Scoring**: ~2 seconds per ticker per analysis
- **Context Detection**: ~1 second per ticker per day

### **External Dependencies**:
- **Reddit API**: Free tier (100 requests/minute)
- **X API**: Basic tier (~$100/month for comprehensive access)
- **Google Trends**: Free but rate-limited (pytrends handles throttling)

## Implementation Questions & Decisions

### **1. Baseline Storage Strategy** ✅
**Decision**: Pre-calculate and store rolling baselines in `abnormality_baselines` table
**Rationale**: Performance critical for real-time abnormality scoring

### **2. Context Event Sources** ✅  
**Decision**: Multi-source context detection
- yfinance for earnings/dividend calendars
- SEC 8-K filings for earnings call detection
- Cross-ticker correlation for sector events

### **3. Public Sentiment Scope** ✅
**Decision**: Focus on financial subreddits and $TICKER mentions
- Reddit: r/investing, r/SecurityAnalysis, r/ValueInvesting, r/stocks
- X: $TICKER hashtags, financial influencer mentions
- Engagement weighting: Higher upvotes/likes = higher signal weight

### **4. Missing Data Handling** ✅
**Decision**: Confidence-weighted inclusion with clear flags
- Include component even with insufficient baseline data
- Flag as "low_confidence" 
- Adjust composite confidence accordingly

## Success Metrics

### **Functional Requirements**
- ✅ Multi-timeframe abnormality scoring (7d/30d/90d)
- ✅ Context-aware threshold adjustments
- ✅ Both Z-scores and percentiles calculated
- ✅ Public sentiment as core functionality (not optional)
- ✅ Catalyst detection and classification
- ✅ Graceful degradation with missing data

### **Performance Requirements**
- ✅ <10 seconds for complete sentiment analysis per ticker
- ✅ <100ms for abnormality score lookup (cached baselines)
- ✅ Daily baseline updates for all active tickers
- ✅ Real-time context event detection

## Recommendation

**PROCEED with enhanced abnormality-based architecture** implementing all requested features:

1. **Multi-timeframe analysis** (7/30/90-day windows)
2. **Context awareness** (earnings, dividends, calls)  
3. **Public sentiment as core** (Reddit/X integration)
4. **Both Z-scores and percentiles** for comprehensive abnormality detection
5. **Individual component scoring** with detailed abnormality metrics

This creates a **state-of-the-art sentiment analysis system** that detects market abnormalities before they become widely recognized, while maintaining our local-first, auditable principles.

**Ready to implement SNT1B-SNT5 with this enhanced architecture when you approve!** 🚀

---

**Next Steps**: 
1. SNT1B: Google Trends integration with abnormality detection
2. SNT1C: Insider trading integration with transaction pattern analysis  
3. SNT1D: Public sentiment integration (Reddit/X APIs)
4. SNT2: Baseline management and abnormality scoring engine
5. SNT3: Context awareness and calendar integration
