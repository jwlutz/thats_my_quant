# Enhanced MetricsJSON v2 Schema

## Overview

Enhanced MetricsJSON v2 extends the original MetricsJSON with formatted display strings, deterministic classifications, and audit indices for hallucination-free LLM integration.

## Core Principles

1. **Single Source of Truth**: All raw numbers preserved from v1
2. **Display Ready**: Pre-formatted strings for consistent presentation
3. **LLM Friendly**: Small interpretive labels to guide narrative
4. **Audit Enabled**: Complete index of allowed narrative elements
5. **Deterministic**: Same input always produces same v2 output

## Schema Definition

```json
{
  "meta": {
    "ticker": "AAPL",
    "company": "Apple Inc.",
    "exchange": "NASDAQ",
    "currency": "USD",
    "as_of_local": "2025-09-07T15:00:00-07:00",
    "as_of_utc": "2025-09-07T22:00:00Z",
    "timezone": "America/Los_Angeles",
    "run_id": 1234,
    "sources": ["yfinance", "sec_edgar"],
    "schema_version": "2.0.0"
  },
  "price": {
    "current": {
      "value": 229.87,
      "display": "$229.87",
      "date": "2025-09-05",
      "date_display": "September 5, 2025"
    },
    "returns": {
      "windows": ["1D", "1W", "1M", "3M", "6M", "1Y"],
      "raw": {
        "1D": 0.0123,
        "1W": 0.018,
        "1M": 0.0891,
        "3M": 0.054,
        "6M": 0.102,
        "1Y": 0.148
      },
      "display": {
        "1D": "1.2%",
        "1W": "1.8%", 
        "1M": "8.9%",
        "3M": "5.4%",
        "6M": "10.2%",
        "1Y": "14.8%"
      },
      "best_period": "1M",
      "worst_period": "1D"
    },
    "volatility": {
      "window_days": 21,
      "raw": 0.2845,
      "display": "28.5%",
      "level": "moderate",
      "window_display": "(21-day)"
    },
    "drawdown": {
      "max_dd_raw": -0.1845,
      "max_dd_display": "-18.5%",
      "peak_date": "2025-07-15",
      "peak_date_display": "July 15, 2025",
      "trough_date": "2025-08-12", 
      "trough_date_display": "August 12, 2025",
      "recovery_date": "2025-08-28",
      "recovery_date_display": "August 28, 2025",
      "recovered": true,
      "duration_days": 28,
      "recovery_status": "fully recovered"
    }
  },
  "ownership_13f": {
    "as_of": "2025-06-30",
    "as_of_display": "June 30, 2025",
    "total_value": {
      "raw": 125000000000.0,
      "display": "$125.0B"
    },
    "total_holders": 145,
    "concentration": {
      "basis": "CR5",
      "level": "moderate",
      "cr1": {"raw": 0.12, "display": "12.0%"},
      "cr5": {"raw": 0.37, "display": "37.0%"},
      "cr10": {"raw": 0.52, "display": "52.0%"},
      "hhi": {"raw": 0.045, "display": "0.045"}
    },
    "top_holders": [
      {
        "rank": 1,
        "filer": "VANGUARD GROUP INC",
        "value_raw": 12300000000.0,
        "value_display": "$12.3B",
        "share_of_total_raw": 0.084,
        "share_of_total_display": "8.4%"
      }
    ],
    "disclaimer": "13F reflects reported long U.S. positions with reporting lag; not total float."
  },
  "data_quality": {
    "price_coverage": {"raw": 0.985, "display": "98.5%"},
    "missing_days": 3,
    "13f_age_days": 45,
    "limitations": ["quarterly_13f_lag", "weekend_gaps_normal"]
  },
  "footnotes": [
    "Volatility annualized with √252.",
    "No back-adjustment of OHLCV; adj_close reported if available.",
    "13F data has 45-day regulatory filing lag."
  ],
  "audit_index": {
    "percent_strings": ["1.2%", "1.8%", "8.9%", "5.4%", "10.2%", "14.8%", "28.5%", "-18.5%", "12.0%", "37.0%", "52.0%", "0.045", "98.5%", "8.4%"],
    "currency_strings": ["$229.87", "$125.0B", "$12.3B"],
    "dates": ["September 5, 2025", "July 15, 2025", "August 12, 2025", "August 28, 2025", "June 30, 2025"],
    "labels": ["low", "moderate", "high", "CR5", "HHI", "fully recovered"],
    "numbers": [229.87, 125.0, 12.3, 145, 28, 45, 3],
    "windows": ["(21-day)", "1-day", "1-month", "3-month", "6-month", "1-year"]
  }
}
```

## Classification Thresholds (Deterministic)

### Volatility Levels (Annualized)
```python
def classify_vol_level(ann_vol: float) -> str:
    if ann_vol < 0.20:      # < 20%
        return "low"
    elif ann_vol <= 0.35:   # 20-35%
        return "moderate"
    else:                   # > 35%
        return "high"
```

### Concentration Levels
**Prefer CR5 when available, fallback to HHI:**

```python
def classify_concentration(concentration_data: dict) -> dict:
    # Prefer CR5
    if concentration_data.get('cr5') is not None:
        cr5 = concentration_data['cr5']
        if cr5 < 0.25:
            level = "low"
        elif cr5 <= 0.40:
            level = "moderate"
        else:
            level = "high"
        return {"level": level, "basis": "CR5"}
    
    # Fallback to HHI
    elif concentration_data.get('hhi') is not None:
        hhi = concentration_data['hhi']
        if hhi < 0.10:
            level = "low"
        elif hhi <= 0.18:
            level = "moderate"
        else:
            level = "high"
        return {"level": level, "basis": "HHI"}
    
    else:
        return {"level": "unknown", "basis": "insufficient_data"}
```

## Formatting Standards

### Percentages
- **Format**: 1 decimal place
- **Examples**: "28.5%", "-18.5%", "1.2%"
- **Negative**: Include minus sign

### Currency
- **Large amounts**: Use B/M notation
- **Examples**: "$125.0B", "$12.3M", "$1,234"
- **Threshold**: >$1B use B, >$1M use M

### Dates
- **Format**: "Month D, YYYY"
- **Examples**: "July 15, 2025", "August 12, 2025"
- **No abbreviations**: Full month names

### Windows
- **Format**: "(N-day)" for volatility windows
- **Examples**: "(21-day)", "(252-day)"
- **Period labels**: "1-day", "1-month", "1-year" for returns

## Audit Index Purpose

The `audit_index` contains every string, number, date, and label that the LLM is allowed to use in narrative generation. Any element not in this index indicates hallucination.

### Audit Categories
- **percent_strings**: All formatted percentages
- **currency_strings**: All formatted dollar amounts
- **dates**: All formatted dates
- **labels**: All classification labels
- **numbers**: All raw numbers (for flexibility)
- **windows**: All time window descriptions

## Migration from v1

Enhanced v2 is generated from existing MetricsJSON v1:
1. **Preserve all raw values** from v1
2. **Add formatted display strings** using deterministic formatters
3. **Add classification labels** using threshold functions
4. **Build audit index** from all formatted elements
5. **Add metadata** for provenance and validation

## Validation Rules

### Schema Compliance
- All v1 fields preserved in raw form
- All display fields are strings
- All labels are predefined values only
- Audit index contains all formatted elements

### Data Consistency
- Raw and display values must correspond
- Classifications must match threshold rules
- Audit index must be complete and accurate
- No external data or interpretations added

## Usage in LLM Prompts

```
System: "You are a neutral financial analyst. Use ONLY the provided v2 JSON."

User: "Write executive summary using the display fields and labels. Do not change any numbers or add new ones. All allowed values are in audit_index."
```

The LLM receives rich, structured data with formatting already applied, reducing the chance of calculation errors or hallucinated figures.
