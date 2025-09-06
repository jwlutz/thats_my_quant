# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added - 2024-12-19

#### T2: Normalizers
- Implemented normalize_prices and normalize_13f pure transformation functions
- Created golden test fixtures for AAPL prices and Berkshire 13F data
- Applied minimal normalization: date parsing, field mapping, CIK padding, value units
- All normalizations justified and documented with rationale
- Primary key deduplication prevents DB constraint violations

#### T1: Core Validators
- Implemented validate_prices_row and validate_13f_row pure functions
- Added comprehensive validation for required keys, types, and numeric constraints
- Implemented check_price_date_monotonicity for date sequence validation
- All validators fail closed on invalid data (no silent errors)

#### T0: Schema Contracts
- Created SCHEMAS.md with canonical row shapes for prices, holdings_13f, and runs tables
- Added schema contract tests with type validation and fixtures
- Established primary keys and constraints for each table
- Documented provenance fields (source, as_of, ingested_at) for traceability

#### Initial Project Scaffold
- Created comprehensive Cursor Rules system in `.cursor/rules/`
  - `core.mdc`: 95% confidence gate, no hallucinations policy
  - `planning.mdc`: Living documentation requirements
  - `git.mdc`: Commit standards and practices
  - `testing.mdc`: Snapshot testing and golden data
  - `security.mdc`: Secrets management and security practices
  - `data.mdc`: Schema definitions and data integrity
  - `reporting.mdc`: Report structure and LLM boundaries
- Created `AGENTS.md` with operating principles
- Established planning framework:
  - `plan.md`: MVP task graph and milestones
  - `assumptions.md`: Technical and business assumptions
  - `risks.md`: Risk register with mitigation strategies
  - This changelog
- Set up Architecture Decision Records (ADR) system

### Planned

#### Phase 1: Foundation (Day 1)
- [ ] Complete project directory structure
- [ ] Create .gitignore and .env.example
- [ ] Set up git repository with initial commit
- [ ] Create ADR-0001 for local-first architecture

#### Phase 2: Data Layer (Day 2)
- [ ] SQLite database with runs, prices, holdings_13f tables
- [ ] Adapt existing 13F scraper to new architecture
- [ ] Build yfinance ingestion pipeline
- [ ] Implement data validation layer

#### Phase 3: Analysis Engine (Day 3)
- [ ] Calculate returns (1D to 1Y)
- [ ] Compute volatility metrics
- [ ] Calculate maximum drawdown
- [ ] Build 13F concentration analytics

#### Phase 4: Reporting (Day 4)
- [ ] Markdown report generator
- [ ] Ollama integration for narrative
- [ ] Report versioning system
- [ ] Metadata tracking

#### Phase 5: Polish (Day 5)
- [ ] CLI interface
- [ ] Golden ticker tests
- [ ] Documentation
- [ ] Performance optimization

## Decision Log

### 2024-12-19: Project Architecture
- **Decision**: Local-first with SQLite + file storage
- **Rationale**: Simplicity, no cloud dependencies, user control
- **Trade-offs**: Single user, limited scalability
- **Alternative**: Cloud-based → rejected for complexity

### 2024-12-19: LLM Strategy
- **Decision**: Ollama for narrative only, no calculations
- **Rationale**: Prevent hallucinations, ensure accuracy
- **Trade-offs**: More code for calculations
- **Alternative**: Let LLM calculate → rejected for accuracy

### 2024-12-19: Rule System
- **Decision**: .cursor/rules/ with MDC format
- **Rationale**: Modern Cursor approach, better organization
- **Trade-offs**: Requires Cursor IDE
- **Alternative**: .cursorrules → deprecated format

## Metrics

### Code Quality
- Lines of Code: TBD
- Test Coverage: Target 80%
- Linter Warnings: Target 0

### Performance
- Report Generation: Target <30s
- Data Fetch: Target <10s per ticker
- Database Queries: Target <100ms

### Data Quality
- Price Coverage: Target >95%
- 13F Parse Success: Target >99%
- Validation Pass Rate: Target 100%

## Lessons Learned

### What Went Well
- Comprehensive rule system established upfront
- Clear scope definition prevents feature creep
- Existing 13F scraper provides solid foundation

### What Could Improve
- TBD after implementation begins

### Action Items
- Set up monitoring for risk indicators
- Create backup data sources
- Plan for user feedback collection

## Version History

- **0.0.1** (Unreleased) - Initial scaffold and planning
- **0.1.0** (Planned) - MVP with basic functionality
- **0.2.0** (Future) - Add news integration
- **0.3.0** (Future) - Add valuation metrics
- **1.0.0** (Future) - Production ready

---

*Last Updated: 2024-12-19*
*Next Review: End of Day 1*
