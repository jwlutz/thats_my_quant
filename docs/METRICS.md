# Financial Metrics Specification

## Overview

This document defines the exact JSON schema for all financial metrics calculated by the analysis engine.
All metrics are deterministic and traceable to source data.

## MetricsJSON Schema

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
      "1D": 0.0234,     // 2.34% (decimal format)
      "1W": -0.0156,    // -1.56%
      "1M": 0.0891,     // 8.91%
      "3M": 0.1245,     // 12.45%
      "6M": 0.0678,     // 6.78%
      "1Y": 0.2134      // 21.34%
    },
    "volatility": {
      "21D_annualized": 0.2845,  // 28.45% annualized
      "63D_annualized": 0.3124,  // 31.24% annualized
      "252D_annualized": 0.2967  // 29.67% annualized
    },
    "drawdown": {
      "max_drawdown_pct": -0.1845,        // -18.45%
      "peak_date": "2025-07-15",
      "trough_date": "2025-08-12", 
      "recovery_date": "2025-08-28",      // null if not recovered
      "drawdown_days": 28,
      "recovery_days": 16                 // null if not recovered
    },
    "current_price": {
      "close": 229.87,
      "date": "2025-09-05"
    }
  },
  "institutional_metrics": {
    "total_13f_value_usd": 1234567890.0,
    "total_13f_holders": 145,
    "concentration": {
      "cr1": 0.0456,    // Top 1 holder owns 4.56%
      "cr5": 0.1234,    // Top 5 holders own 12.34%
      "cr10": 0.2345,   // Top 10 holders own 23.45%
      "hhi": 0.0123     // Herfindahl-Hirschman Index
    },
    "top_holders": [
      {
        "rank": 1,
        "filer": "VANGUARD GROUP INC", 
        "value_usd": 56789012.0,
        "shares": 987654,
        "pct_of_13f_total": 0.0456  // 4.56%
      }
      // ... up to 10 holders
    ],
    "quarter_end": "2024-09-30",
    "filing_lag_days": 45
  },
  "data_quality": {
    "price_coverage_pct": 98.5,          // % of expected trading days
    "missing_price_days": 3,
    "latest_13f_quarter": "2024-09-30",
    "13f_data_age_days": 45
  },
  "metadata": {
    "calculated_at": "2025-09-06T14:30:00",
    "calculation_version": "1.0.0",
    "data_sources": ["yfinance", "sec_edgar"]
  }
}
```

## Field Definitions

### Returns
- **Format**: Decimal (0.0234 = 2.34%)
- **Calculation**: Simple returns: `(P_t / P_{t-k}) - 1`
- **Windows**: 1D=1, 1W=5, 1M=21, 3M=63, 6M=126, 1Y=252 trading days
- **Price Used**: `close` (not `adj_close` for MVP)

### Volatility
- **Format**: Annualized decimal (0.2845 = 28.45%)
- **Calculation**: Rolling standard deviation of log returns × √252
- **Windows**: 21D (1M), 63D (3M), 252D (1Y)
- **Log Returns**: `ln(P_t) - ln(P_{t-1})`

### Drawdown
- **max_drawdown_pct**: Largest peak-to-trough decline (negative decimal)
- **peak_date**: Date of peak before drawdown
- **trough_date**: Date of lowest point
- **recovery_date**: Date when price exceeded peak again (null if not recovered)
- **drawdown_days**: Days from peak to trough
- **recovery_days**: Days from trough to recovery (null if not recovered)

### 13F Concentration
- **CR1, CR5, CR10**: Concentration ratios (top N holders' share of total 13F value)
- **HHI**: Herfindahl-Hirschman Index = Σ(share_i²) for all holders
- **Base**: `value_usd` (not share count)
- **Scope**: 13F institutions only (not total float)

## Data Requirements

### Minimum Data for Metrics
- **1D/1W returns**: 2+ trading days
- **1M returns**: 22+ trading days  
- **3M returns**: 64+ trading days
- **6M returns**: 127+ trading days
- **1Y returns**: 253+ trading days
- **Volatility**: Same as return requirements
- **Drawdown**: 10+ trading days (meaningful)
- **13F concentration**: 1+ holders with valid data

### Missing Data Policy
- **Insufficient data**: Return `null` for that metric
- **Partial data**: Calculate what's possible, note limitations
- **No data**: Return empty metrics with clear indicators

## Units and Precision
- **Returns**: 4 decimal places (0.1234 = 12.34%)
- **Volatility**: 4 decimal places (0.2845 = 28.45%)
- **Drawdown**: 4 decimal places (0.1845 = 18.45%)
- **Concentration**: 4 decimal places (0.0456 = 4.56%)
- **Dollar Values**: Integer dollars (no cents)
- **Dates**: ISO format YYYY-MM-DD

## Validation Rules
- All percentages as decimals (not 12.34, but 0.1234)
- No NaN or infinite values in output
- Dates must be valid trading dates from source data
- All calculations must be reproducible
- Missing metrics explicitly marked as `null`
