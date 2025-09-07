# Data Flow Documentation

## Overview

This document describes the complete data flow through the AI Stock Market Research Workbench, from external APIs to final research reports.

## Architecture Diagram

```
┌─────────────────┐    ┌─────────────────┐
│   External      │    │   External      │
│   APIs          │    │   APIs          │
│                 │    │                 │
│  ┌─────────┐    │    │  ┌─────────┐    │
│  │yfinance │    │    │  │SEC EDGAR│    │
│  │(Yahoo)  │    │    │  │(13F)    │    │
│  └─────────┘    │    │  └─────────┘    │
└─────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌─────────────────┐
│   Providers     │    │   Providers     │
│                 │    │                 │
│  yfinance_      │    │  sec_13f_       │
│  adapter.py     │    │  adapter.py     │
└─────────────────┘    └─────────────────┘
         │                       │
         ▼                       ▼
┌─────────────────────────────────────────┐
│            Transforms                   │
│                                         │
│  ┌─────────────┐    ┌─────────────┐    │
│  │normalizers  │    │ validators  │    │
│  │   .py       │    │   .py       │    │
│  └─────────────┘    └─────────────┘    │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│              Storage                    │
│                                         │
│  ┌─────────────┐    ┌─────────────┐    │
│  │SQLite       │    │Run Registry │    │
│  │(prices,     │    │(tracking)   │    │
│  │ holdings)   │    │             │    │
│  └─────────────┘    └─────────────┘    │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│            Analysis                     │
│                                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │Returns  │ │Volatility│ │Drawdown │   │
│  └─────────┘ └─────────┘ └─────────┘   │
│  ┌─────────┐ ┌─────────────────────┐   │
│  │13F Conc.│ │  Metrics Aggregator │   │
│  └─────────┘ └─────────────────────┘   │
└─────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│             Output                      │
│                                         │
│  ┌─────────────┐    ┌─────────────┐    │
│  │MetricsJSON  │    │ Markdown    │    │
│  │Files        │    │ Reports     │    │
│  └─────────────┘    └─────────────┘    │
└─────────────────────────────────────────┘
```

## Data Pipeline Stages

### Stage 1: Data Ingestion

#### Price Data (yfinance → SQLite)
```bash
python pipeline/run.py daily_prices AAPL 30
```

**Flow**:
1. `yfinance_adapter.py` fetches OHLCV data from Yahoo Finance
2. `normalizers.py` converts to canonical format (date parsing, field mapping)
3. `validators.py` validates price logic (high >= low, positive prices)
4. `loaders.py` upserts to SQLite `prices` table (idempotent)
5. `run_registry.py` tracks execution with metrics

**Input**: Ticker + date range
**Output**: Validated price records in SQLite
**Rate Limits**: None (yfinance is free)

#### Holdings Data (SEC EDGAR → SQLite)
```bash
python pipeline/run.py quarterly_13f "BERKSHIRE HATHAWAY INC" 2024-09-30
```

**Flow**:
1. `sec_13f_adapter.py` wraps existing `data_extraction.py` scraper
2. Scraper fetches 13F XML from SEC EDGAR
3. `normalizers.py` converts to canonical format (CIK padding, ticker inference)
4. `validators.py` validates holdings data (non-negative values, CUSIP format)
5. `loaders.py` upserts to SQLite `holdings_13f` table (idempotent)
6. `run_registry.py` tracks execution with metrics

**Input**: Institution name/CIK + quarter end date
**Output**: Validated holdings records in SQLite
**Rate Limits**: 10 requests/second (SEC policy)
**Authentication**: Requires SEC_USER_AGENT header

### Stage 2: Data Analysis

#### Financial Metrics Calculation
```bash
python analysis/analyze_ticker.py AAPL
```

**Flow**:
1. `analysis_job.py` queries SQLite for ticker data
2. `returns.py` calculates simple returns over multiple windows
3. `volatility.py` calculates log returns and realized volatility
4. `drawdown.py` analyzes peak-to-trough declines and recovery
5. `concentration.py` calculates institutional ownership metrics
6. `metrics_aggregator.py` composes all calculations into MetricsJSON
7. Results saved to `data/processed/metrics/{ticker}.json`

**Input**: Ticker symbol
**Output**: Complete MetricsJSON file
**Dependencies**: Requires price data in SQLite

### Stage 3: Report Generation

#### Markdown Reports
```bash
python reports/render_report.py AAPL
```

**Flow**:
1. Load MetricsJSON from `data/processed/metrics/{ticker}.json`
2. `markdown_template.py` renders structured Markdown
3. Optional: LLM integration for narrative sections
4. Save to `reports/{ticker}/{date}_metrics.md`

**Input**: Ticker symbol (must have calculated metrics)
**Output**: Human-readable Markdown report

## Data Schemas

### prices Table
```sql
PRIMARY KEY (ticker, date)
```
- **Source**: yfinance API
- **Frequency**: Daily trading data
- **Retention**: Indefinite (historical analysis)

### holdings_13f Table  
```sql
PRIMARY KEY (cik, cusip, as_of)
```
- **Source**: SEC EDGAR 13F filings
- **Frequency**: Quarterly (45-day filing lag)
- **Retention**: Indefinite (trend analysis)

### runs Table
```sql
PRIMARY KEY (run_id)
```
- **Source**: Pipeline execution tracking
- **Frequency**: Per pipeline run
- **Retention**: 1 year (operational monitoring)

## Data Quality Controls

### Input Validation
- **Price data**: High >= Low, positive values, valid dates
- **13F data**: Non-negative values, valid CUSIPs, proper CIK format
- **Date ranges**: No future dates, reasonable bounds

### Processing Validation
- **Returns**: Check for infinite/NaN values
- **Volatility**: Validate standard deviation calculations
- **Drawdown**: Verify peak-trough logic
- **Concentration**: Ensure ratios sum correctly

### Output Validation
- **MetricsJSON**: Schema compliance
- **Numeric bounds**: Reasonable ranges for all metrics
- **Data freshness**: Age warnings for stale data

## Error Handling

### Graceful Degradation
- Missing 13F data → price-only analysis
- Insufficient data → calculate available metrics only
- API failures → cached data with warnings

### Stop-and-Ask Triggers
- <150 trading days for 1Y analysis
- >5% conflicting 13F rows
- NaN/infinite values in calculations
- Unrealistic returns (>1000%)

## Performance Characteristics

### Typical Execution Times
- **Price ingestion**: 1-3 seconds per ticker
- **13F ingestion**: 3-10 seconds per institution
- **Metrics calculation**: <1 second per ticker
- **Report generation**: <1 second per ticker

### Storage Requirements
- **Price data**: ~50 bytes per ticker-day
- **13F data**: ~200 bytes per holding
- **Metrics**: ~5KB per ticker analysis
- **Reports**: ~10-50KB per ticker report

### Scalability Limits
- **SQLite**: Suitable for <1M price records
- **Memory**: Analysis engine uses <100MB RAM
- **Disk I/O**: Optimized for SSD storage

## Monitoring and Observability

### Run Tracking
- Every pipeline execution logged with:
  - Start/end timestamps
  - Input/output row counts
  - Success/failure status
  - Error messages

### Data Quality Metrics
- Price coverage percentage
- 13F data freshness
- Validation failure rates
- Missing data indicators

### Performance Monitoring
- Pipeline execution times
- Database query performance
- Memory usage patterns
- API response times

## Configuration

### Environment Variables
```bash
# Required for 13F
SEC_USER_AGENT="Your Name your.email@example.com"

# Optional tuning
SEC_RATE_LIMIT_RPS=5
YFINANCE_TIMEOUT=30
LOG_LEVEL=INFO
```

### File Locations
```
data/
├── research.db              # Main SQLite database
├── cache/                   # Temporary API responses
├── processed/metrics/       # MetricsJSON files
└── logs/                    # Application logs

reports/
└── {ticker}/               # Generated reports by ticker
    ├── {date}_metrics.md   # Metrics report
    └── {date}_full.md      # Full research report
```

## Data Lineage

Every data point includes:
- **source**: Data provider (yfinance, sec_edgar)
- **as_of**: Market date of the data
- **ingested_at**: When pipeline processed it

This enables full traceability and reproducibility of all analysis.

## Future Enhancements

### Planned Features
- News sentiment integration
- Valuation metrics (P/E, P/B ratios)
- Sector/industry comparisons
- Options data analysis

### Scalability Improvements
- PostgreSQL migration for larger datasets
- Distributed processing for bulk analysis
- Real-time data streaming
- Cloud storage integration

---

*Last Updated: 2025-09-06*
*Next Review: After Phase 4 completion*
