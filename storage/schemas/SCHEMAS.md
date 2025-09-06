# Data Schemas

## Overview

This document defines the canonical schemas for all data tables in the AI Stock Market Research Workbench.
All data transformations must produce rows conforming to these schemas.

## Tables

### prices

Stores daily OHLCV price data for equities.

```sql
CREATE TABLE prices (
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    adj_close REAL,  -- Optional: adjusted close price
    volume INTEGER NOT NULL,
    source TEXT NOT NULL,  -- Data provider (e.g., 'yfinance')
    as_of DATE NOT NULL,   -- Market date of the data
    ingested_at DATETIME NOT NULL,  -- When we fetched/stored it
    PRIMARY KEY (ticker, date)
);
```

**Canonical Row Shape (Python dict)**:
```python
{
    'ticker': str,           # e.g., 'AAPL'
    'date': date,           # Trading date
    'open': float,          # Opening price
    'high': float,          # High price
    'low': float,           # Low price
    'close': float,         # Closing price
    'adj_close': float|None,  # Adjusted close (optional)
    'volume': int,          # Trading volume
    'source': str,          # e.g., 'yfinance'
    'as_of': date,          # Data date (usually same as date)
    'ingested_at': datetime,  # Pipeline timestamp
}
```

**Constraints**:
- `high >= low`
- `high >= open`, `high >= close`
- `low <= open`, `low <= close`
- `volume >= 0`
- All price values > 0

### holdings_13f

Stores institutional holdings from quarterly 13F filings.

```sql
CREATE TABLE holdings_13f (
    cik TEXT NOT NULL,           -- Central Index Key of filer
    filer TEXT NOT NULL,          -- Institution name
    ticker TEXT NOT NULL,         -- Stock ticker
    name TEXT NOT NULL,           -- Company name
    cusip TEXT NOT NULL,          -- CUSIP identifier
    value_usd REAL NOT NULL,      -- Position value in USD
    shares REAL NOT NULL,         -- Number of shares
    as_of DATE NOT NULL,          -- Reporting period end date
    source TEXT NOT NULL,         -- Data source (e.g., 'sec_edgar')
    ingested_at DATETIME NOT NULL,  -- When we fetched/stored it
    PRIMARY KEY (cik, cusip, as_of)
);
```

**Canonical Row Shape (Python dict)**:
```python
{
    'cik': str,             # e.g., '0001067983' (padded to 10 digits)
    'filer': str,           # e.g., 'BERKSHIRE HATHAWAY INC'
    'ticker': str,          # e.g., 'AAPL'
    'name': str,            # e.g., 'APPLE INC'
    'cusip': str,           # e.g., '037833100'
    'value_usd': float,     # Position value in USD
    'shares': float,        # Share count
    'as_of': date,          # Quarter end date
    'source': str,          # e.g., 'sec_edgar'
    'ingested_at': datetime,  # Pipeline timestamp
}
```

**Constraints**:
- `value_usd >= 0`
- `shares >= 0`
- CIK is typically 10 digits (left-padded with zeros)
- CUSIP is 9 characters

### runs

Tracks pipeline execution history and metrics.

```sql
CREATE TABLE runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    dag_name TEXT NOT NULL,         -- Pipeline/DAG identifier
    started_at DATETIME NOT NULL,   -- Run start time
    finished_at DATETIME,           -- Run end time (NULL if running)
    status TEXT NOT NULL,           -- 'running', 'completed', 'failed'
    rows_in INTEGER,                -- Input row count
    rows_out INTEGER,               -- Output row count
    log_path TEXT                   -- Path to detailed log file
);
```

**Canonical Row Shape (Python dict)**:
```python
{
    'run_id': int,          # Auto-generated ID
    'dag_name': str,        # e.g., 'daily_prices'
    'started_at': datetime,  # Run start
    'finished_at': datetime|None,  # Run end (None if running)
    'status': str,          # One of: 'running', 'completed', 'failed'
    'rows_in': int|None,    # Input count
    'rows_out': int|None,   # Output count
    'log_path': str|None,   # Log file location
}
```

**Constraints**:
- `status` must be one of: `'running'`, `'completed'`, `'failed'`
- `finished_at` is NULL while `status = 'running'`
- `finished_at` is set when status changes to `'completed'` or `'failed'`

## Data Provenance

Every table includes provenance fields:
- `source`: Identifies the data provider (e.g., 'yfinance', 'sec_edgar')
- `as_of`: The actual date of the data (market date for prices, reporting period for 13F)
- `ingested_at`: When our pipeline processed/stored the data

This allows full traceability and reproducibility of all data.

## Primary Keys

- **prices**: `(ticker, date)` - One price per ticker per trading day
- **holdings_13f**: `(cik, cusip, as_of)` - One holding per institution per security per quarter
- **runs**: `run_id` - Auto-incrementing identifier

## Notes on Normalization

Following the principle of minimal normalization, we only transform data when necessary:

1. **Ticker symbols**: Stored as provided by the data source (no forced uppercasing unless required)
2. **CIK padding**: 13F CIKs are padded to 10 digits for consistency with SEC format
3. **Dates**: Stored as DATE type for market dates, DATETIME for timestamps
4. **Numeric precision**: REAL (float) for prices and values, INTEGER for volumes

Any additional normalization must be justified and documented in the transform functions.
