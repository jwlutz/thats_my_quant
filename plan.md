# AI Stock Market Research Workbench - Project Plan

## Current Sprint: MVP Foundation
**Goal**: Local-first research workbench with yfinance + 13F data → metrics → Markdown reports

## Objectives
- [ ] Set up clean, testable workspace with proper structure
- [ ] Integrate existing 13F scraper with new architecture
- [ ] Build yfinance OHLCV ingestion pipeline
- [ ] Implement core metrics (returns, volatility, drawdown)
- [ ] Create Markdown report generator with LLM narrative
- [ ] Set up SQLite database for run tracking
- [ ] Build CLI for single-ticker report generation

## Constraints
- **Scope**: MVP only - no web UI, cloud services, or trading
- **Dependencies**: Minimal (yfinance, pandas, sqlite3, requests)
- **LLM**: Ollama/OpenWebUI for narrative only
- **Data**: Local-first, no external storage
- **Time**: Focus on working MVP over perfect architecture

## Acceptance Criteria
- [ ] Can run: `python cli.py report AAPL` and get Markdown report
- [ ] Report includes: prices, returns, volatility, 13F holdings
- [ ] All calculations deterministic and traceable
- [ ] LLM provides narrative without inventing numbers
- [ ] Run logged to database with status and paths
- [ ] Can list previous runs and retrieve reports
- [ ] Passes golden ticker snapshot tests

## Task Graph

### Phase 1: Foundation (Current)
1. **Project Scaffolding** ✅
   - [x] Create .cursor/rules/ with 7 MDC files
   - [x] Create AGENTS.md
   - [ ] Create planning documents
   - [ ] Create decisions/ADR-0001.md
   - [ ] Set up directory structure
   - [ ] Create .gitignore and .env.example

### Phase 2: Data Layer (TDD Micro-Steps)

#### T0 — Schema Contracts (no code, no IO) ✅
**Goal**: Freeze canonical row shapes & PKs in SCHEMAS.md + schema contract tests.
**Acceptance**:
- [x] SCHEMAS.md lists `prices`, `holdings_13f`, `runs` exactly as defined
- [x] Add tiny fixture dicts and a schema test that asserts keys/types (no DB)
**Deliverables**: updated SCHEMAS.md; tests red→green; commit: `feat(data): T0 schema contracts & schema tests`

#### T1 — Core Validators (pure) ✅
**Goal**: Deterministic validators for canonical rows.
**Functions**:
- [x] `validate_prices_row(row) -> None|Error`
- [x] `validate_13f_row(row) -> None|Error`
**Properties**: required keys present; numerics finite; separate helper to check date monotonicity per ticker.
**Tests**: unit + property tests; fail closed on missing/extra keys or invalid numerics.
**Commit**: `feat(data): T1 validators for prices & 13F`

#### T2 — Normalizers (pure; minimal normalization) ✅
**Goal**: Transform provider-native rows → canonical shapes with ONLY necessary coercions.
**Functions**:
- [x] `normalize_prices(raw_rows, *, ticker, source, as_of) -> list[canonical]`
- [x] `normalize_13f(raw_rows, *, source, as_of) -> list[canonical]`
**Rules**:
- [x] Do not uppercase/trim if provider output is already normalized or schema accepts it
- [x] Only normalize when justified (comment + plan.md note)
**Tests**: Golden fixtures (AAPL 2 days; tiny 13F snapshot). Exact canonical output; PK uniqueness.
**Commit**: `feat(data): T2 normalizers with golden fixtures`

**Normalizations Applied (Justified)**:
- Date strings → date objects (schema requirement)
- Field name mapping (provider uses "Date", "Open" vs canonical "date", "open")
- CIK padding to 10 digits (SEC standard format)
- 13F values: thousands → dollars (consistent units)
- Primary key deduplication (prevents DB constraint violations)
- Ticker inference from issuer name (enables price-holdings joins)

#### T3 — Loader Idempotence (thin IO, SQLite) ✅
**Goal**: Idempotent upsert writers.
**Functions**:
- [x] `upsert_prices(rows) -> (inserted:int, updated:int)`
- [x] `upsert_13f(rows) -> (inserted:int, updated:int)`
- [x] `init_database(conn)` - creates tables with indices
- [x] `upsert_run()` - for run tracking
**Tests**: In-memory SQLite; two consecutive upserts yield identical table state; PK uniqueness.
**Commit**: `feat(data): T3 sqlite upsert loaders with idempotence tests`

#### T4 — yfinance Adapter (provider; network allowed, mocked in tests) ✅
**Goal**: Windowed fetch without business logic or "cleanup."
**Function**:
- [x] `fetch_prices_window(ticker, start, end) -> list[raw_rows]`
- [x] Input validation (date range, ticker format)
- [x] Error handling with custom YFinanceError
**Tests**: Mock network; assert shape only. No live calls in CI.
**Commit**: `feat(data): T4 yfinance adapter (mocked tests)`

#### T5 — 13F Adapter Wrapper (over existing data_extraction.py) ✅
**Goal**: Stable interface around our scraper; do not rewrite.
**Function**:
- [x] `fetch_13f_quarter(entity_name|cik, *, quarter_end) -> list[raw_rows]`
- [x] Quarter-end date validation and filing deadline calculation
- [x] Environment variable configuration (SEC_USER_AGENT required)
**Requirements**:
- [x] Use existing scraper's call pattern; do not change internals unless absolutely required
- [x] If EDGAR headers/rate-limits needed, STOP and add minimal .env.example entries
- [x] Surface `as_of` from filing; set `source='sec_edgar'`
- [x] Avoid unnecessary normalization; return scraper's shape
**Tests**: Fixture from scraper's parsed output → adapter returns expected raw shape.
**Commit**: `feat(data): T5 13F adapter over existing scraper + minimal .env`

#### T6 — runs Registry & Metrics (thin IO) ✅
**Goal**: Create/run/close rows; capture counts + status + log path.
**Functions**:
- [x] `start_run(dag_name) -> run_id`
- [x] `finish_run(run_id, status, rows_in, rows_out, log_path) -> None`
- [x] `get_run_status(run_id)` - detailed run info with computed metrics
- [x] `list_recent_runs()` - recent runs with filtering and limits
- [x] `get_dag_stats()` - aggregate statistics for DAG performance
**Tests**: In-memory DB; status transitions; timestamps set; counts correct.
**Commit**: `feat(data): T6 runs registry with metrics`

#### T7 — DAG: daily_prices (orchestration only) ✅
**Goal**: Compose adapter → normalizer → validator → loader with logging.
**Spec**:
- [x] `DailyPricesConfig` with ticker, start_date, end_date (default: last 365 days)
- [x] `run_daily_prices(config, conn) -> summary dict`
- [x] `pipeline/run.py` CLI for human-visible execution
**Function**:
- [x] Complete pipeline: fetch → normalize → validate → store → track
- [x] Error handling with graceful failure and run tracking
- [x] Metrics calculation (price ranges, returns, volume)
- [x] Idempotent execution (safe to retry)
**Tests**: Integration using mocked adapter + real normalizer/loader; assert row counts and runs row.
**Commit**: `feat(data): T7 daily_prices DAG + integration test`

#### T8 — DAG: quarterly_13f (orchestration only) ✅
**Goal**: Provider → normalizer → validator → loader; quarterly cadence.
**Spec**:
- [x] `Quarterly13FConfig` with entity_name/cik + quarter_end validation
- [x] `run_quarterly_13f(config, conn) -> summary dict`
- [x] Updated CLI runner to support both daily_prices and quarterly_13f
**Function**:
- [x] Complete pipeline: fetch 13F → normalize → validate → store → track
- [x] Holdings metrics calculation (concentration, top positions, total value)
- [x] Support for both entity name and CIK lookup
- [x] Idempotent execution using existing scraper
**Tests**: Integration test; assert PK uniqueness (cik, cusip, as_of) and proper runs logging.
**Commit**: `feat(data): T8 quarterly_13f DAG + integration test`

### Phase 3: Analysis Engine (TDD Micro-Steps)

#### A0 — Metrics Contracts & Fixtures (pure, no I/O) ✅
**Goal**: Define exact JSON shapes for outputs + add tiny golden fixtures.
**Deliverables**:
- [x] docs/METRICS.md with field names, units, windows
- [x] Fixtures: tests/fixtures/prices_aapl_small.csv, tests/fixtures/holdings_13f_tiny.json, expected metrics JSON
- [x] Tests: schema/shape tests read fixtures and assert expected keys & types (no DB)
**Commit**: `feat(analysis): A0 metrics contracts & fixtures`

#### A1 — Returns Utilities (pure) ✅
**Goal**: Calculate simple returns over trading day windows.
**Functions**:
- [x] `window_ends(trading_dates, windows=[1,5,21,63,126,252]) -> dict`
- [x] `simple_returns(series, k) -> float` (and vectorized helper)
- [x] `calculate_period_returns()` - multi-window calculator
**Tests**: Deterministic synthetic series where you can hand-verify 1D/1W/etc.
**Commit**: `feat(analysis): A1 returns utilities`

#### A2 — Log Returns & Realized Volatility (pure) ✅
**Goal**: Calculate log returns and rolling volatility.
**Functions**:
- [x] `log_returns(series) -> np.ndarray`
- [x] `realized_vol(log_ret, window=21, annualize=252) -> float`
- [x] `rolling_volatility()` - rolling windows
- [x] `calculate_volatility_metrics()` - multi-window calculator
**Tests**: Synthetic series with known std; rolling checks; NaN handling policy explicit.
**Commit**: `feat(analysis): A2 log returns & volatility`

#### A3 — Drawdown & Recovery (pure) ✅
**Goal**: Calculate maximum drawdown and recovery periods.
**Functions**:
- [x] `drawdown_stats(series) -> {max_dd, peak_date, trough_date, recovery_date|null}`
- [x] `rolling_drawdown()` - rolling window analysis
- [x] `calculate_drawdown_metrics()` - with data sufficiency checks
**Tests**: Crafted series with one big dip and later recovery; assert dates & %.
**Commit**: `feat(analysis): A3 drawdown & recovery`

#### A4 — 13F Concentration (pure) ✅
**Goal**: Calculate institutional ownership concentration metrics.
**Functions**:
- [x] `concentration_ratios(value_by_holder: dict) -> {cr1, cr5, cr10}`
- [x] `herfindahl_index()` - HHI calculation
- [x] `calculate_concentration_metrics()` - complete analysis
- [x] `analyze_13f_holdings()` - process holdings list for ticker
**Tests**: Tiny dict fixtures where CRn/HHI are easy to verify by hand.
**Commit**: `feat(analysis): A4 13F concentration`

#### A5 — Metric Aggregator (pure) ✅
**Goal**: Compose all metrics into single JSON output.
**Functions**:
- [x] `compose_metrics(price_df, holdings_df|null, as_of_date|null) -> MetricsJSON`
- [x] Complete integration of returns, volatility, drawdown, and concentration
- [x] Data quality assessment and metadata generation
**Tests**: Feed AAPL fixture + tiny 13F fixture; assert combined JSON matches golden.
**Commit**: `feat(analysis): A5 metric aggregator`

#### A6 — Orchestrated Analysis Job (thin I/O) ✅
**Goal**: Query SQLite for ticker + date window, call pure functions, persist analysis JSON.
**Functions**:
- [x] `analyze_ticker()` - complete SQLite to MetricsJSON pipeline
- [x] `_query_price_data()` and `_query_holdings_data()` - database queries
- [x] `batch_analyze_tickers()` - multi-ticker analysis
- [x] Persist to `data/processed/metrics/{ticker}.json`
**Tests**: Temp DB seeded with fixture rows; output file equals golden; deterministic.
**Commit**: `feat(analysis): A6 analysis orchestration`

#### A7 — CLI/Task Entry Points (thin I/O)
**Goal**: Human-visible commands for metric calculation.
**Commands**:
- [ ] `analyze_ticker TICKER --start YYYY-MM-DD --end YYYY-MM-DD`
- [ ] `show_metrics TICKER` (prints path + short summary)
**Tests**: Subprocess call in temp workspace with seeded DB; assert exit code and output.
**Commit**: `feat(analysis): A7 CLI entry points`

#### A8 — Guardrails & Docs Polish ✅
**Goal**: Add validation and documentation.
**Features**:
- [x] Stop-and-Ask checks: missing 150+ trading days when 1Y required
- [x] Conflicting duplicate 13F rows detection
- [x] NaN/infinite input validation
- [x] Data freshness warnings and price integrity checks
- [x] Complete guardrail system with recommendations
- [x] Update DATAFLOW.md with analysis workflows
**Commit**: `feat(analysis): A8 guardrails & documentation`

### Path 2 Stub: Report Shell (After A5)

#### R0 — Markdown View Template (pure)
**Goal**: Jinja/Markdown template that renders MetricsJSON.
**Features**:
- [ ] Tables for returns, volatility, drawdown, concentration
- [ ] Unit test: known MetricsJSON → golden .md file
**Commit**: `feat(reports): R0 markdown template`

#### R1 — render_report TICKER (thin I/O)
**Goal**: Read MetricsJSON and write formatted report.
**Functions**:
- [ ] `render_report(ticker)` → reads metrics JSON, writes `/reports/{ticker}/{date}_metrics.md`
**Tests**: Seeded file → assert exact content matches expected.
**Commit**: `feat(reports): R1 report renderer`

## Future Development Strategy

### Phase 4: Enhanced JSON + AI Reports (Current Sprint)

#### EJ0 — v2 Schema & Fixtures (pure)
**Goal**: Define Enhanced MetricsJSON v2 schema with formatted values and interpretations.
**Deliverables**:
- [ ] docs/METRICS_V2.md (schema + classification thresholds)
- [ ] Golden v2 fixtures (AAPL, MSFT)
- [ ] Schema/shape tests only
**Commit**: `feat(reports): EJ0 v2 schema & fixtures`

#### EJ1 — Labelers (pure)
**Goal**: Deterministic classification functions for volatility and concentration levels.
**Functions**:
- [ ] `classify_vol_level(ann_vol)` - low <20%, moderate 20-35%, high >35%
- [ ] `classify_concentration(conc)` - prefer CR5, fallback HHI with thresholds
**Tests**: Threshold boundaries and edge cases.
**Commit**: `feat(reports): EJ1 classification labelers`

#### EJ2 — Formatter (pure)
**Goal**: Deterministic string formatting for display values.
**Functions**:
- [ ] Format percentages (1 decimal), dates (Month D, YYYY), currency ($12.3B)
- [ ] Consistent formatting across all metrics
**Tests**: Deterministic formatting with edge cases.
**Commit**: `feat(reports): EJ2 display formatters`

#### EJ3 — v1→v2 Builder (pure)
**Goal**: Convert existing MetricsJSON to Enhanced v2 format with audit index.
**Functions**:
- [ ] `build_enhanced_metrics_v2(metrics_v1) -> metrics_v2`
- [ ] Populate audit_index with all allowed strings/numbers
- [ ] Apply labelers and formatters
**Tests**: Fixture v1 → expected v2 exactly.
**Commit**: `feat(reports): EJ3 v1 to v2 builder`

#### EJ4 — Exec-Summary Skeleton (pure)
**Goal**: Build executive summary skeleton with all data pre-filled.
**Functions**:
- [ ] `build_exec_summary_skeleton(v2) -> str`
- [ ] Handle missing fields with "Not available"
- [ ] Include volatility, drawdown, concentration per policy
**Tests**: Fixture → exact expected skeleton string.
**Commit**: `feat(reports): EJ4 executive summary skeleton`

#### EJ5 — LLM Polisher (thin I/O)
**Goal**: Polish skeleton for readability without changing any data.
**Implementation**:
- [ ] Reuse Ollama client with System/Developer/User prompts
- [ ] Enforce 120-180 words (truncate if needed)
- [ ] No number/date changes allowed
**Tests**: Mocked responses; word count enforcement.
**Commit**: `feat(reports): EJ5 LLM polisher`

#### EJ6 — Number/Date Audit (pure)
**Goal**: Audit LLM output against v2 audit_index for hallucinations.
**Functions**:
- [ ] `audit_narrative(text, v2) -> bool|diagnostic`
- [ ] Tolerance: ±0.1pp on percentage formatting
- [ ] Extract and verify all numbers/dates
**Tests**: Pass/fail scenarios with tolerance testing.
**Commit**: `feat(reports): EJ6 number audit system`

#### EJ7 — Composer & CLI (thin I/O)
**Goal**: Complete report generation with tables + narrative.
**Implementation**:
- [ ] Merge data tables + AI narrative into full report
- [ ] Write to `reports/{TICKER}/{timestamp}_report.md`
- [ ] Update latest.md and latest_reports.json
- [ ] CLI: `python cli.py report AAPL`
**Tests**: Golden markdown output; atomic writes; idempotence.
**Commit**: `feat(reports): EJ7 complete report system`

**Timeline**: 2-3 days for complete AI report generation system

### Phase L: LangChain Integration (Current)

#### LC0 — Dependency & Env Guard (pure)
**Goal**: Add minimal LangChain deps: `langchain-core`, `langchain-ollama`. Keep telemetry off unless `LANGSMITH_TRACING=true`.
**Acceptance**:
- [ ] `requirements.txt` scoped deps (no unintended integrations)
- [ ] Startup check warns if tracing env is set; otherwise remains disabled
- [ ] `docs/THOUGHTLOG.md` entry: why LC is limited to polish-only
**Tests**:
- [ ] Import tests pass without optional backends
- [ ] Env gate test confirms tracing is off by default
**Commit**: `feat(langchain): LC0 minimal deps + env guard`

#### LC1 — Exec Summary Chain (LCEL)
**Goal**: Build a chain: System/Developer/User prompts → `OllamaLLM` → parser that enforces "one paragraph, 120–180 words".
**Input**: v2 MetricsJSON (or a stub fixture if v2 not done yet) + pre-filled skeleton string from our builder
**Output**: single paragraph string
**Acceptance**:
- [ ] Length enforced; structure parseable; fails closed on format drift
- [ ] `docs/THOUGHTLOG.md`: why LCEL + parser approach; alternatives considered
**Tests**:
- [ ] Fixtures → success; over/under-length cases → retry once then truncate/decline per policy
**Commit**: `feat(langchain): LC1 exec-summary chain with structured parser`

#### LC2 — Number/Date Audit Runnable (pure) 
**Goal**: Wrap LC1 output with an audit that extracts numbers/dates and ensures they are a subset of `audit_index`.

**Acceptance Criteria (Go/No-Go)**:
- [ ] **Extraction Rules (Deterministic)**:
  - [ ] Percentages: `r'[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?\s?%'`
  - [ ] Dates: `r'(January|February|...|December)\s+\d{1,2},\s+\d{4}'` (strict Month D, YYYY)
  - [ ] Numbers: Only audit percentages and dates (no plain decimals unless explicitly allowed)
- [ ] **Normalization for Compare**:
  - [ ] Percent tokens → float: strip %, remove thousands separators, parse to float
  - [ ] Tolerance: ±0.05 percentage points (abs(model−source) ≤ 0.0005)
  - [ ] Dates: parse with dateutil to YYYY-MM-DD and check set membership
- [ ] **audit_index Enhancement**:
  - [ ] `numeric_percents`: raw floats (e.g., 0.285, -0.185, 0.37)
  - [ ] `dates_iso`: YYYY-MM-DD format for comparison
- [ ] **Algorithm**: extract → normalize → compare
  - [ ] If all tokens ∈ allowed sets (within tolerance) → pass
  - [ ] Else: retry once (same skeleton, same prompts)
  - [ ] If still failing → fallback to skeleton and log WARN with offending tokens
- [ ] **Edge Cases Tested**:
  - [ ] Negative percent -18.5% survives; -0.0% normalized to 0.0%
  - [ ] Multiple identical numbers in text are ok
  - [ ] Dates with leading zeros (August 05, 2025) normalized and pass
  - [ ] Smart quotes vs straight quotes don't affect audit
- [ ] **Performance**: Fast execution (no NLP heuristics, pure regex + numeric comparison)

**Tests**: Positive/negative cases; tolerance edges; all edge cases above
**Commit**: `feat(langchain): LC2 numeric/date audit + fallback`

#### LC3 — Risks Bullets Chain (LCEL)
**Goal**: Chain that outputs **3–5 bullets**; parser enforces list-of-strings with length bounds; audit numbers/dates like LC2.
**Acceptance**:
- [ ] Exactly 3–5 bullets; no new numbers/dates
- [ ] `docs/THOUGHTLOG.md` update: design choices
**Tests**:
- [ ] Fixtures hit min/max; bad-format retry then fallback
**Commit**: `feat(langchain): LC3 risks bullets chain with parser & audit`

#### LC4 — CLI Glue & Switch
**Goal**: `report TICKER --llm=on|off` gates calling LC1/LC3; default off.
**Acceptance**:
- [ ] When `--llm=off`: deterministic tables only
- [ ] When `--llm=on`: invokes chains; on audit failure → skeleton fallback
- [ ] Update `docs/DECISIONS/ADR-00XX.md` ("LangChain limited to polish-only")
**Tests**:
- [ ] CLI e2e with fixtures; exit codes; idempotent output
**Commit**: `feat(langchain): LC4 CLI switch + e2e tests`

### Phase SNT: Sentiment Analysis (After LangChain)

#### SNT0 — ADR & Scope Definition
**Goal**: Define sentiment analysis architecture and scope
**Acceptance**:
- [ ] Create `decisions/ADR-00XX.md` for sentiment approach
- [ ] RSS-first strategy with optional external providers
- [ ] Local FinBERT model for sentiment classification
- [ ] Integration with v2 MetricsJSON schema
**Commit**: `feat(sentiment): SNT0 architecture decision record`

#### SNT1 — RSS News Ingestion
**Goal**: Ingest news from RSS feeds for ticker-specific sentiment
**Functions**:
- [ ] `fetch_rss_news(ticker, days=7)` - RSS feed aggregation
- [ ] `parse_news_items()` - extract title, content, date, source
- [ ] RSS source configuration in `config/rss_sources.yml`
**Tests**:
- [ ] Mock RSS responses; parse various feed formats
**Commit**: `feat(sentiment): SNT1 RSS news ingestion pipeline`

#### SNT2 — Optional News Providers (OpenBB/NewsAPI)
**Goal**: Optional integration with external news APIs
**Functions**:
- [ ] `fetch_openbb_news()` - OpenBB integration
- [ ] `fetch_newsapi_news()` - NewsAPI integration
- [ ] Provider fallback chain with rate limiting
**Tests**:
- [ ] Mocked provider responses; credential validation
**Commit**: `feat(sentiment): SNT2 optional news providers`

#### SNT3 — News Normalization & Storage
**Goal**: Normalize news from all sources and store in SQLite
**Schema**: `news` table with ticker, title, content, source, published_date, sentiment_score
**Functions**:
- [ ] `normalize_news_item()` - canonical format
- [ ] `upsert_news()` - idempotent storage
**Tests**:
- [ ] Schema validation; deduplication logic
**Commit**: `feat(sentiment): SNT3 news normalization & storage`

#### SNT4 — Local Sentiment Classification
**Goal**: Local FinBERT model for financial sentiment scoring
**Functions**:
- [ ] `classify_sentiment(text)` - FinBERT inference
- [ ] `batch_classify_news()` - efficient batch processing
- [ ] Model download and caching
**Tests**:
- [ ] Known financial text → expected sentiment scores
**Commit**: `feat(sentiment): SNT4 local sentiment classifier`

#### SNT5 — Sentiment Aggregation
**Goal**: Aggregate news sentiment into ticker-level metrics
**Functions**:
- [ ] `aggregate_sentiment_metrics(ticker, days=7)` - time-weighted scoring
- [ ] `sentiment_trend_analysis()` - trend detection
- [ ] Integration with existing MetricsJSON
**Tests**:
- [ ] Synthetic news data → expected aggregations
**Commit**: `feat(sentiment): SNT5 sentiment aggregation metrics`

#### SNT6 — Report Section Integration
**Goal**: Add sentiment section to reports with LLM narrative
**Features**:
- [ ] Sentiment metrics in v2 MetricsJSON
- [ ] LangChain chain for sentiment narrative
- [ ] Integration with existing report generation
**Tests**:
- [ ] End-to-end report with sentiment section
**Commit**: `feat(sentiment): SNT6 report integration`

#### SNT7 — CLI Commands
**Goal**: Human-visible sentiment commands
**Commands**:
- [ ] `sentiment TICKER --days=7` - show sentiment metrics
- [ ] `news TICKER --days=7` - show recent news items
**Tests**:
- [ ] CLI e2e with mocked data
**Commit**: `feat(sentiment): SNT7 CLI commands`

#### SNT8 — Caching & Performance
**Goal**: Optimize sentiment pipeline performance
**Features**:
- [ ] News item caching with TTL
- [ ] Batch sentiment processing
- [ ] Rate limiting for external APIs
**Tests**:
- [ ] Performance benchmarks; cache hit rates
**Commit**: `feat(sentiment): SNT8 caching & performance`

### Phase 5: Advanced Features (Future)
**Potential Enhancements:**
- Valuation metrics (P/E, P/B ratios)
- Sector/industry comparisons
- Portfolio-level analysis
- Historical trend analysis

### Phase 6: Production Polish (Future)
**Potential Improvements:**
- Bulk operations for multiple tickers
- Automated daily data collection
- Performance monitoring dashboard
- Advanced data quality checks
- Report scheduling and alerts

## Legacy Planning (Superseded by Current Implementation)

*The sections below were from the original plan and have been superseded by the actual implementation in Phases 1-3. Keeping for historical reference.*

## Milestones

| Milestone | Target | Success Criteria |
|-----------|--------|------------------|
| M1: Foundation | Day 1 | Rules, structure, planning docs complete |
| M2: Data Pipeline | Day 2 | Can fetch and store price/13F data |
| M3: Analysis | Day 3 | Metrics calculated correctly |
| M4: Reporting | Day 4 | Full report generation working |
| M5: Polish | Day 5 | Tests passing, docs complete |

## Current Status: FOUNDATION COMPLETE ✅

### What We've Built (Phases 1-3 Complete)
- ✅ **Rock-solid data pipeline**: yfinance + SEC EDGAR → SQLite
- ✅ **Complete analysis engine**: Returns, volatility, drawdown, 13F concentration
- ✅ **Production CLI tools**: Data collection and analysis commands
- ✅ **Report storage infrastructure**: Ticker libraries with atomic operations
- ✅ **Real Ollama integration**: Working LLM client with your models

### Next Phase Strategy (ADR-0003)
**Enhanced MetricsJSON for LLM Integration**
- Enhance current MetricsJSON with formatted values and interpretations
- Create LLM-readable structured data (not prose templates)
- Build narrative generation from enhanced JSON
- Foundation for multi-section reports and sentiment integration

### Immediate Commands Available
```bash
# Data Collection
python pipeline/run.py daily_prices AAPL 60
python pipeline/run.py quarterly_13f "BERKSHIRE HATHAWAY INC" 2024-12-31

# Financial Analysis  
python analysis/analyze_ticker.py AAPL
python analysis/show_metrics.py AAPL

# Database Inspection
python check_db.py
```

## Non-Goals (Explicitly Out of Scope)

- ❌ Web interface or API
- ❌ Real-time data streaming
- ❌ Price predictions or targets
- ❌ Portfolio optimization
- ❌ Multi-user support
- ❌ Cloud deployment
- ❌ News sentiment analysis
- ❌ Options data
- ❌ International markets
- ❌ Cryptocurrency
