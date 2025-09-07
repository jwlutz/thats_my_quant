# Report Schema Specification

## Report Structure (Fixed Order)

All research reports follow this exact section order:

### 1. Title Block
```markdown
# Stock Research Report: {TICKER}

**Company:** {Company Name}  
**Currency:** USD  
**Price Data:** {start_date} to {end_date} ({trading_days} days)  
**13F Data:** As of {quarter_end} ({filing_lag} days ago)  
**Generated:** {timestamp}  
**Report ID:** {run_id}
```

### 2. Executive Summary
**Source**: LLM-generated (120-180 words, single paragraph)
**Input**: Complete MetricsJSON
**Constraints**: 
- Synthesizes Price Snapshot and Ownership Snapshot
- Mentions largest drawdown and recent volatility with window
- Notes concentration level (high/low)
- No bullets, no price targets, no speculation

### 3. Price Snapshot
**Source**: Tables rendered from MetricsJSON
**Tables**:
- Returns by window (1D, 1W, 1M, 3M, 6M, 1Y)
- Volatility (21D, 63D, 252D annualized)
- Maximum drawdown with recovery info

### 4. Ownership Snapshot  
**Source**: Tables rendered from MetricsJSON
**Tables**:
- Concentration ratios (CR1, CR5, CR10, HHI)
- Top 10 institutional holders with values and percentages

### 5. Risks & Watchlist
**Source**: LLM-generated (3-5 bullets)
**Input**: MetricsJSON only
**Constraints**:
- Bullets grounded ONLY in available data
- Examples: elevated volatility, unrecovered drawdown, high concentration
- No external context or speculation

### 6. Appendix
**Source**: Tables rendered from MetricsJSON
**Content**:
- Data sources and freshness
- Run ID and generation timestamp
- Data quality metrics
- Disclaimer

## MetricsJSON Contract (Source of Truth)

```json
{
  "ticker": "AAPL",
  "as_of_date": "2025-09-06", 
  "data_period": {
    "start_date": "2024-09-06",
    "end_date": "2025-09-06", 
    "trading_days": 252
  },
  "price_metrics": {
    "returns": {
      "1D": 0.0123,
      "1W": -0.0045,
      "1M": 0.0891,
      "3M": 0.1234,
      "6M": 0.0567,
      "1Y": 0.2134
    },
    "volatility": {
      "21D_annualized": 0.2845,
      "63D_annualized": 0.3124, 
      "252D_annualized": 0.2967
    },
    "drawdown": {
      "max_drawdown_pct": -0.1845,
      "peak_date": "2025-07-15",
      "trough_date": "2025-08-12",
      "recovery_date": "2025-08-28",
      "drawdown_days": 28,
      "recovery_days": 16
    },
    "current_price": {
      "close": 229.87,
      "date": "2025-09-05"
    }
  },
  "institutional_metrics": {
    "total_13f_value_usd": 123456789000.0,
    "total_13f_holders": 145,
    "concentration": {
      "cr1": 0.0456,
      "cr5": 0.1234,
      "cr10": 0.2345,
      "hhi": 0.0123
    },
    "top_holders": [
      {
        "rank": 1,
        "filer": "VANGUARD GROUP INC",
        "value_usd": 5678901234.0,
        "shares": 25000000,
        "pct_of_13f_total": 0.0456
      }
    ],
    "quarter_end": "2024-09-30",
    "filing_lag_days": 45
  },
  "data_quality": {
    "price_coverage_pct": 98.5,
    "missing_price_days": 3,
    "latest_13f_quarter": "2024-09-30", 
    "13f_data_age_days": 45
  },
  "metadata": {
    "calculated_at": "2025-09-06T14:30:00",
    "calculation_version": "1.0.0",
    "data_sources": ["yfinance", "sec_edgar"],
    "run_id": 123
  }
}
```

## LLM Prompt Contracts

### System Prompt (Constant)
```
You are a neutral equity research analyst. Use ONLY the provided JSON data. Do not invent numbers, dates, or facts. Cite dates in parentheses when referring to metrics. No price targets or investment recommendations. If a field is missing, write "Not available." Keep writing concise and factual.
```

### Developer Prompt (Constant)
```
You will receive a single JSON object named METRICS. You must produce Markdown for the requested section ONLY, without restating tables that will be rendered separately. Do not compute new values; interpret what's present. Avoid speculation about future performance.
```

### User Prompts (Per Section)

**Executive Summary**:
```
Write a single 120-180 word paragraph synthesizing the Price Snapshot and Ownership Snapshot from METRICS. Mention the largest drawdown and the most recent volatility figure with its window, and whether institutional concentration appears high or low based on the CR ratios. No bullet points.
```

**Risks & Watchlist**:
```
List 3-5 bullet points identifying risks grounded ONLY in METRICS data. Examples: elevated volatility levels, recent drawdowns not yet recovered, high institutional concentration ratios. Use specific numbers from METRICS with dates. No external market context.
```

## Anti-Hallucination Guards

### Number Audit Process
1. Parse generated narrative for all numeric tokens
2. Verify each number appears in METRICS (exact match or within 0.1% tolerance)
3. Verify each date appears in METRICS
4. If audit fails: replace with "Not available" and re-prompt once
5. If still fails: drop the offending section

### Validation Rules
- **Word count**: Executive Summary 120-180 words
- **Bullet count**: Risks 3-5 bullets
- **No speculation**: No "will", "should", "expected", "likely"
- **No recommendations**: No "buy", "sell", "hold", "target"
- **Date citations**: All metrics referenced with dates

## File Naming Convention

```
reports/{ticker}/{YYYY-MM-DD_HHMM}_report.md
```

Examples:
- `reports/AAPL/2025-09-06_1430_report.md`
- `reports/MSFT/2025-09-06_1445_report.md`

## Error Handling

### Missing Data
- Missing price metrics: "Price analysis not available"
- Missing 13F data: "Institutional ownership data not available"
- Missing individual metrics: "Not available" in tables

### LLM Failures
- Model unavailable: Use template-only report
- Timeout: Retry once, then use template
- Hallucination detected: Replace with "Analysis pending" and log warning

### File System
- Directory creation: Auto-create report directories
- Existing files: Append timestamp to avoid overwrites
- Permissions: Graceful failure with clear error message
