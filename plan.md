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

#### T3 — Loader Idempotence (thin IO, SQLite)
**Goal**: Idempotent upsert writers.
**Functions**:
- [ ] `upsert_prices(rows) -> (inserted:int, updated:int)`
- [ ] `upsert_13f(rows) -> (inserted:int, updated:int)`
**Tests**: In-memory SQLite; two consecutive upserts yield identical table state; PK uniqueness.
**Commit**: `feat(data): T3 sqlite upsert loaders with idempotence tests`

#### T4 — yfinance Adapter (provider; network allowed, mocked in tests)
**Goal**: Windowed fetch without business logic or "cleanup."
**Function**:
- [ ] `fetch_prices_window(ticker, start, end) -> list[raw_rows]`
**Tests**: Mock network; assert shape only. No live calls in CI.
**Commit**: `feat(data): T4 yfinance adapter (mocked tests)`

#### T5 — 13F Adapter Wrapper (over existing data_extraction.py)
**Goal**: Stable interface around our scraper; do not rewrite.
**Function**:
- [ ] `fetch_13f_quarter(ticker, *, quarter_end) -> list[raw_rows]`
**Requirements**:
- [ ] Use existing scraper's call pattern; do not change internals unless absolutely required
- [ ] If EDGAR headers/rate-limits needed, STOP and add minimal .env.example entries
- [ ] Surface `as_of` from filing; set `source='sec_edgar'`
- [ ] Avoid unnecessary normalization; return scraper's shape
**Tests**: Fixture from scraper's parsed output → adapter returns expected raw shape.
**Commit**: `feat(data): T5 13F adapter over existing scraper + minimal .env`

#### T6 — runs Registry & Metrics (thin IO)
**Goal**: Create/run/close rows; capture counts + status + log path.
**Functions**:
- [ ] `start_run(dag_name) -> run_id`
- [ ] `finish_run(run_id, status, rows_in, rows_out, log_path) -> None`
**Tests**: In-memory DB; status transitions; timestamps set; counts correct.
**Commit**: `feat(data): T6 runs registry with metrics`

#### T7 — DAG: daily_prices (orchestration only)
**Goal**: Compose adapter → normalizer → validator → loader with logging.
**Spec**:
- [ ] pipeline/dags/daily_prices.yml with {tickers, start, end} (default: last 365 calendar days)
**Function**:
- [ ] `run_daily_prices(spec) -> summary dict`
**Tests**: Integration using stubbed adapter + real normalizer/loader; assert row counts and runs row.
**Commit**: `feat(data): T7 daily_prices DAG + integration test`

#### T8 — DAG: quarterly_13f (orchestration only)
**Goal**: Provider → normalizer → validator → loader; quarterly cadence.
**Spec**:
- [ ] {tickers, quarter_end}
**Tests**: Integration test; assert PK uniqueness (cik, cusip, as_of) and proper runs logging.
**Commit**: `feat(data): T8 quarterly_13f DAG + integration test`

### Phase 3: Analysis Engine
4. **Metrics Calculator** (2 hours)
   - [ ] Returns (1D, 1W, 1M, 3M, 6M, 1Y)
   - [ ] Realized volatility (annualized)
   - [ ] Maximum drawdown
   - [ ] 13F concentration metrics
   - [ ] Data coverage statistics

### Phase 4: Reporting
5. **Report Generator** (3 hours)
   - [ ] Create Markdown template
   - [ ] Build data-to-table formatters
   - [ ] Integrate Ollama for narrative
   - [ ] Add metadata sections
   - [ ] Implement versioning

6. **LLM Integration** (2 hours)
   - [ ] Define prompt contracts
   - [ ] Build Ollama client
   - [ ] Create response validator
   - [ ] Add fallback for LLM failures
   - [ ] Enforce word limits

### Phase 5: Orchestration
7. **Run Registry** (1 hour)
   - [ ] Create run tracking
   - [ ] Status management
   - [ ] Error logging
   - [ ] Report path linking

8. **CLI Interface** (2 hours)
   - [ ] `run_report TICKER` command
   - [ ] `list_runs` command
   - [ ] `latest_report TICKER` command
   - [ ] Configuration management
   - [ ] Progress indicators

### Phase 6: Quality Assurance
9. **Testing Suite** (2 hours)
   - [ ] Unit tests for calculations
   - [ ] Golden ticker snapshots (AAPL, MSFT, SPY)
   - [ ] Integration tests
   - [ ] Data validation tests
   - [ ] Report comparison tests

10. **Documentation** (1 hour)
    - [ ] README with quick start
    - [ ] API documentation
    - [ ] Configuration guide
    - [ ] Troubleshooting section

## Milestones

| Milestone | Target | Success Criteria |
|-----------|--------|------------------|
| M1: Foundation | Day 1 | Rules, structure, planning docs complete |
| M2: Data Pipeline | Day 2 | Can fetch and store price/13F data |
| M3: Analysis | Day 3 | Metrics calculated correctly |
| M4: Reporting | Day 4 | Full report generation working |
| M5: Polish | Day 5 | Tests passing, docs complete |

## Next Actions

1. Finish planning documents (assumptions.md, risks.md, changelog.md)
2. Create ADR-0001 for local-first architecture
3. Set up project directory structure
4. Create .gitignore and .env.example
5. Begin database schema implementation

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
