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

### news_raw

Stores raw news items from all sources before processing.

```sql
CREATE TABLE news_raw (
    url_hash TEXT PRIMARY KEY,
    canonical_url TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    published_at DATETIME NOT NULL,
    source TEXT NOT NULL,
    author TEXT,
    fetched_at DATETIME NOT NULL,
    ticker_hint TEXT
);
```

**Canonical Row Shape (Python dict)**:
```python
{
    'url_hash': str,        # SHA-256 hash of canonical_url
    'canonical_url': str,   # Normalized URL
    'title': str,          # Article title
    'body': str|None,      # Article content (optional)
    'published_at': datetime,  # Publication timestamp
    'source': str,         # Source identifier (e.g., 'reuters_rss')
    'author': str|None,    # Author name (optional)
    'fetched_at': datetime,  # When we fetched it
    'ticker_hint': str|None,  # Ticker mentioned in URL/source
}
```

### news_clean

Stores processed and normalized news items with ticker mapping.

```sql
CREATE TABLE news_clean (
    id TEXT PRIMARY KEY,
    url_hash TEXT NOT NULL,
    ticker TEXT NOT NULL,
    published_at DATETIME NOT NULL,
    source TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK(source_type IN('rss','openbb','api')),
    title TEXT NOT NULL,
    body TEXT,
    dedupe_group TEXT,
    as_of DATE NOT NULL,
    ingested_at DATETIME NOT NULL,
    FOREIGN KEY(url_hash) REFERENCES news_raw(url_hash)
);
```

**Canonical Row Shape (Python dict)**:
```python
{
    'id': str,             # UUID for cleaned news item
    'url_hash': str,       # Reference to news_raw
    'ticker': str,         # Mapped ticker symbol
    'published_at': datetime,  # Publication timestamp
    'source': str,         # Source identifier
    'source_type': str,    # One of: 'rss', 'openbb', 'api'
    'title': str,          # Article title
    'body': str|None,      # Article content
    'dedupe_group': str|None,  # Near-duplicate group ID
    'as_of': date,         # Analysis date
    'ingested_at': datetime,  # Processing timestamp
}
```

### news_sentiment

Stores sentiment classification results for news items.

```sql
CREATE TABLE news_sentiment (
    id TEXT PRIMARY KEY,
    news_id TEXT NOT NULL,
    model TEXT NOT NULL,
    model_version TEXT NOT NULL,
    label TEXT NOT NULL CHECK(label IN('pos','neu','neg')),
    score_pos REAL NOT NULL,
    score_neu REAL NOT NULL,
    score_neg REAL NOT NULL,
    confidence REAL NOT NULL,
    computed_at DATETIME NOT NULL,
    FOREIGN KEY(news_id) REFERENCES news_clean(id)
);
```

**Canonical Row Shape (Python dict)**:
```python
{
    'id': str,             # UUID for sentiment record
    'news_id': str,        # Reference to news_clean
    'model': str,          # Model name (e.g., 'finbert')
    'model_version': str,  # Model version
    'label': str,          # Primary label: 'pos', 'neu', 'neg'
    'score_pos': float,    # Positive score (0.0-1.0)
    'score_neu': float,    # Neutral score (0.0-1.0)
    'score_neg': float,    # Negative score (0.0-1.0)
    'confidence': float,   # Overall confidence (0.0-1.0)
    'computed_at': datetime,  # When sentiment was computed
}
```

### sentiment_snapshot

Stores aggregated sentiment metrics for tickers over time windows.

```sql
CREATE TABLE sentiment_snapshot (
    ticker TEXT NOT NULL,
    as_of DATE NOT NULL,
    window_days INTEGER NOT NULL,
    
    -- News sentiment
    news_count INTEGER NOT NULL DEFAULT 0,
    news_avg_score REAL,
    news_pos_pct REAL,
    news_neu_pct REAL,
    news_neg_pct REAL,
    news_confidence REAL,
    
    -- Institutional sentiment (from 13F deltas)
    inst_score REAL,
    inst_confidence REAL,
    
    -- Composite sentiment
    composite_score REAL NOT NULL,
    composite_confidence REAL NOT NULL,
    
    -- Metadata
    catalysts JSON,
    data_quality JSON,
    computed_at DATETIME NOT NULL,
    
    PRIMARY KEY(ticker, as_of, window_days)
);
```

**Canonical Row Shape (Python dict)**:
```python
{
    'ticker': str,         # Stock ticker
    'as_of': date,         # Analysis date
    'window_days': int,    # Sentiment window (e.g., 7, 30)
    'news_count': int,     # Number of news items
    'news_avg_score': float|None,  # Average news sentiment (-1.0 to +1.0)
    'news_pos_pct': float|None,    # % positive news
    'news_neu_pct': float|None,    # % neutral news  
    'news_neg_pct': float|None,    # % negative news
    'news_confidence': float|None,  # Average confidence
    'inst_score': float|None,      # Institutional sentiment score
    'inst_confidence': float|None,  # Institutional confidence
    'composite_score': float,      # Overall sentiment (-1.0 to +1.0)
    'composite_confidence': float,  # Overall confidence (0.0 to 1.0)
    'catalysts': dict|None,        # JSON: identified catalysts
    'data_quality': dict|None,     # JSON: quality metrics
    'computed_at': datetime,       # Computation timestamp
}
```

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
- **news_raw**: `url_hash` - One entry per unique URL
- **news_clean**: `id` - UUID for each processed news item
- **news_sentiment**: `id` - UUID for each sentiment analysis
- **sentiment_snapshot**: `(ticker, as_of, window_days)` - One snapshot per ticker per date per window
- **runs**: `run_id` - Auto-incrementing identifier

## Notes on Normalization

Following the principle of minimal normalization, we only transform data when necessary:

1. **Ticker symbols**: Stored as provided by the data source (no forced uppercasing unless required)
2. **CIK padding**: 13F CIKs are padded to 10 digits for consistency with SEC format
3. **Dates**: Stored as DATE type for market dates, DATETIME for timestamps
4. **Numeric precision**: REAL (float) for prices and values, INTEGER for volumes

Any additional normalization must be justified and documented in the transform functions.
