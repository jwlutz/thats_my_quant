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

### insider_trading

Stores SEC Form 4 insider trading transactions.

```sql
CREATE TABLE insider_trading (
    form_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    company_name TEXT NOT NULL,
    insider_name TEXT NOT NULL,
    insider_title TEXT,
    transaction_date DATE NOT NULL,
    transaction_type TEXT NOT NULL, -- 'buy', 'sell', 'grant', 'exercise'
    shares REAL NOT NULL,
    price_per_share REAL,
    total_value REAL,
    shares_owned_after REAL,
    filing_date DATE NOT NULL,
    source TEXT NOT NULL DEFAULT 'sec_edgar',
    fetched_at DATETIME NOT NULL
);
```

**Canonical Row Shape (Python dict)**:
```python
{
    'form_id': str,        # SEC filing identifier
    'ticker': str,         # Stock ticker
    'company_name': str,   # Company name
    'insider_name': str,   # Name of insider
    'insider_title': str|None,  # Title/position
    'transaction_date': date,    # Date of transaction
    'transaction_type': str,     # 'buy', 'sell', 'grant', 'exercise'
    'shares': float,       # Number of shares
    'price_per_share': float|None,  # Price per share
    'total_value': float|None,      # Total transaction value
    'shares_owned_after': float|None,  # Shares owned after transaction
    'filing_date': date,   # Date of SEC filing
    'source': str,         # Data source
    'fetched_at': datetime,  # When we fetched it
}
```

### public_sentiment

Stores public sentiment data from Reddit and X (Twitter).

```sql
CREATE TABLE public_sentiment (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL CHECK(platform IN('reddit','x')),
    post_id TEXT NOT NULL,
    ticker TEXT NOT NULL,
    author TEXT,
    posted_at DATETIME NOT NULL,
    content TEXT NOT NULL,
    engagement_score REAL, -- upvotes, likes, etc.
    permalink TEXT,
    subreddit TEXT, -- For Reddit posts
    sentiment_label TEXT CHECK(sentiment_label IN('pos','neu','neg')),
    sentiment_score REAL,
    sentiment_confidence REAL,
    fetched_at DATETIME NOT NULL,
    UNIQUE(platform, post_id)
);
```

**Canonical Row Shape (Python dict)**:
```python
{
    'id': str,             # UUID for public sentiment record
    'platform': str,       # 'reddit' or 'x'
    'post_id': str,        # Platform-specific post ID
    'ticker': str,         # Stock ticker
    'author': str|None,    # Username/handle
    'posted_at': datetime, # When posted
    'content': str,        # Post content
    'engagement_score': float|None,  # Upvotes, likes, etc.
    'permalink': str|None, # Link to original post
    'subreddit': str|None, # For Reddit posts
    'sentiment_label': str|None,     # 'pos', 'neu', 'neg'
    'sentiment_score': float|None,   # -1.0 to +1.0
    'sentiment_confidence': float|None,  # 0.0 to 1.0
    'fetched_at': datetime,          # When we fetched it
}
```

### context_events

Stores market context events for abnormality scoring adjustments.

```sql
CREATE TABLE context_events (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK(event_type IN('earnings','dividend_ex','earnings_call','sector_event')),
    event_date DATE NOT NULL,
    event_time DATETIME,
    description TEXT,
    source TEXT NOT NULL,
    metadata JSON, -- Additional event-specific data
    created_at DATETIME NOT NULL,
    UNIQUE(ticker, event_type, event_date)
);
```

**Canonical Row Shape (Python dict)**:
```python
{
    'id': str,             # UUID for context event
    'ticker': str,         # Stock ticker
    'event_type': str,     # 'earnings', 'dividend_ex', 'earnings_call', 'sector_event'
    'event_date': date,    # Date of event
    'event_time': datetime|None,  # Specific time if available
    'description': str|None,      # Event description
    'source': str,         # Data source
    'metadata': dict|None, # Additional event data
    'created_at': datetime,       # When we recorded it
}
```

### abnormality_baselines

Stores rolling baseline statistics for abnormality detection.

```sql
CREATE TABLE abnormality_baselines (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    metric_type TEXT NOT NULL, -- 'search_volume', 'insider_volume', 'news_volume', etc.
    timeframe_days INTEGER NOT NULL, -- 7, 30, 90
    baseline_date DATE NOT NULL,
    mean_value REAL NOT NULL,
    std_value REAL NOT NULL,
    percentiles JSON NOT NULL, -- P10, P25, P50, P75, P90, P95, P99
    data_points INTEGER NOT NULL,
    computed_at DATETIME NOT NULL,
    UNIQUE(ticker, metric_type, timeframe_days, baseline_date)
);
```

**Canonical Row Shape (Python dict)**:
```python
{
    'id': str,             # UUID for baseline record
    'ticker': str,         # Stock ticker
    'metric_type': str,    # Type of metric ('search_volume', 'insider_volume', etc.)
    'timeframe_days': int, # Timeframe (7, 30, 90)
    'baseline_date': date, # Date baseline was calculated for
    'mean_value': float,   # Mean of baseline period
    'std_value': float,    # Standard deviation
    'percentiles': dict,   # P10, P25, P50, P75, P90, P95, P99
    'data_points': int,    # Number of data points in baseline
    'computed_at': datetime,  # When baseline was computed
}
```

### google_trends

Stores Google Trends search interest data for tickers.

```sql
CREATE TABLE google_trends (
    id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    search_term TEXT NOT NULL,
    date DATE NOT NULL,
    search_volume INTEGER NOT NULL, -- 0-100 relative scale
    geo TEXT DEFAULT 'US',
    timeframe TEXT NOT NULL, -- e.g., 'today 7-d', 'today 1-m'
    related_queries JSON,
    rising_queries JSON,
    fetched_at DATETIME NOT NULL,
    UNIQUE(ticker, search_term, date, geo, timeframe)
);
```

**Canonical Row Shape (Python dict)**:
```python
{
    'id': str,             # UUID for trends record
    'ticker': str,         # Stock ticker
    'search_term': str,    # Search term used (ticker or company name)
    'date': date,          # Date of search interest
    'search_volume': int,  # Google Trends volume (0-100)
    'geo': str,            # Geographic region (default: 'US')
    'timeframe': str,      # Timeframe used for query
    'related_queries': dict|None,  # JSON: related search queries
    'rising_queries': dict|None,   # JSON: rising search queries  
    'fetched_at': datetime,        # When we fetched it
}
```

### sentiment_snapshot

Stores aggregated sentiment metrics for tickers over time windows.

```sql
CREATE TABLE sentiment_snapshot (
    ticker TEXT NOT NULL,
    as_of DATE NOT NULL,
    window_days INTEGER NOT NULL,
    
    -- Multi-timeframe abnormality scores (7d, 30d, 90d)
    abnormality_score_7d REAL,
    abnormality_score_30d REAL,
    abnormality_score_90d REAL,
    abnormality_percentile_7d REAL,
    abnormality_percentile_30d REAL,
    abnormality_percentile_90d REAL,
    abnormality_classification TEXT CHECK(abnormality_classification IN('normal','unusual','extreme')),
    
    -- Component abnormality scores
    institutional_abnormality REAL,
    institutional_percentile REAL,
    institutional_classification TEXT,
    
    insider_abnormality REAL,
    insider_percentile REAL,
    insider_classification TEXT,
    insider_transaction_count INTEGER DEFAULT 0,
    insider_net_value REAL,
    
    news_abnormality REAL,
    news_percentile REAL,
    news_classification TEXT,
    news_count INTEGER DEFAULT 0,
    news_avg_sentiment REAL,
    
    search_abnormality REAL,
    search_percentile REAL,
    search_classification TEXT,
    search_volume_current INTEGER,
    search_volume_baseline REAL,
    
    public_abnormality REAL,
    public_percentile REAL,
    public_classification TEXT,
    public_mention_count INTEGER DEFAULT 0,
    public_avg_sentiment REAL,
    
    -- Composite abnormality (weighted across timeframes and components)
    composite_abnormality REAL NOT NULL,
    composite_percentile REAL NOT NULL,
    composite_classification TEXT NOT NULL,
    composite_confidence REAL NOT NULL,
    
    -- Context adjustments
    context_events JSON, -- Active context events affecting scoring
    context_adjustment_factor REAL DEFAULT 1.0,
    
    -- Catalysts and metadata
    catalysts JSON,
    data_quality JSON,
    baseline_sufficiency JSON, -- Which baselines have sufficient data
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
- **insider_trading**: `form_id` - One entry per SEC filing
- **public_sentiment**: `id` - UUID with unique constraint on (platform, post_id)
- **context_events**: `id` - UUID with unique constraint on (ticker, event_type, event_date)
- **abnormality_baselines**: `id` - UUID with unique constraint on (ticker, metric_type, timeframe_days, baseline_date)
- **google_trends**: `id` - UUID with unique constraint on (ticker, search_term, date, geo, timeframe)
- **sentiment_snapshot**: `(ticker, as_of, window_days)` - One snapshot per ticker per date per window
- **runs**: `run_id` - Auto-incrementing identifier

## Notes on Normalization

Following the principle of minimal normalization, we only transform data when necessary:

1. **Ticker symbols**: Stored as provided by the data source (no forced uppercasing unless required)
2. **CIK padding**: 13F CIKs are padded to 10 digits for consistency with SEC format
3. **Dates**: Stored as DATE type for market dates, DATETIME for timestamps
4. **Numeric precision**: REAL (float) for prices and values, INTEGER for volumes

Any additional normalization must be justified and documented in the transform functions.
