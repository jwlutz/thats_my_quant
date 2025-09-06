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

### Phase 2: Data Layer
2. **Database Setup** (2 hours)
   - [ ] Create SQLite schema (runs, prices, holdings_13f)
   - [ ] Build connection manager
   - [ ] Create migration system
   - [ ] Add indices for performance

3. **Ingestion Module** (3 hours)
   - [ ] Adapt existing 13F scraper to new structure
   - [ ] Build yfinance wrapper with error handling
   - [ ] Create data validators
   - [ ] Implement caching layer
   - [ ] Add rate limiting

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
