# Thought Process Log

This document tracks the rationale behind architectural and implementation decisions for maintainers. Each entry includes the goal, options considered, decision made, and reasoning.

## 2025-01-XX - LangChain Integration Strategy (LC0-LC4)

**Goal**: Integrate LangChain for polish-only LLM orchestration while preserving deterministic pipeline

**Options Considered**:
1. Full LangChain agents with tools and memory
2. Direct Ollama integration (current approach)  
3. Minimal LangChain for polish-only chains ✅

**Decision**: Option 3 - Minimal LangChain integration limited to polish-only chains

**Reasoning**:
- Maintains our no-hallucination principle by keeping LLM usage narrow
- LCEL chains provide better structured output parsing than raw Ollama calls
- Audit wrappers can ensure no new numbers/dates are introduced
- Preserves local-first architecture with controlled LLM usage
- CLI flag `--llm=on|off` provides user control over AI features

**Implementation Notes**:
- Only add `langchain-core` and `langchain-ollama` dependencies
- Keep telemetry disabled by default (`LANGSMITH_TRACING=false`)
- Build chains for exec summary (120-180 words) and risk bullets (3-5 items)
- Wrap all chains with number/date audit that validates against v2 audit_index
- Fallback to skeleton on audit failure to maintain deterministic output

**Status**: LC0 COMPLETED - Dependencies added, environment guard implemented with comprehensive tests
**Status**: LC1 COMPLETED - Executive summary chain with LCEL, structured parser (120-180 words), and risk bullets chain implemented with comprehensive test coverage
**Status**: LC1 REFINEMENTS COMPLETED - Added deterministic model params (temp=0), max 1 retry policy, restricted quote cleaning, regex sentence truncation, and comprehensive logging
**Status**: LC2 COMPLETED - Number/date audit system with regex extraction, tolerance-based validation (±0.05pp), fallback to skeleton, and comprehensive integration with both exec summary and risk bullets chains
**Status**: LC3 COMPLETED - Risk bullets chain already integrated with same audit system as exec summary (3-5 bullets, format validation, audit fallback)
**Status**: LC4 COMPLETED - CLI integration with --llm=on|off switch (default off), argparse support, risk analysis section, graceful LLM failure handling

**Links**: Related to ADR-0003 Enhanced MetricsJSON strategy

---

## 2025-01-XX - Sentiment Analysis Architecture (SNT0)

**Goal**: Define sentiment analysis architecture with multi-source local-first approach

**Options Considered**:
1. News-only sentiment (RSS + FinBERT)
2. External sentiment APIs (NewsAPI, Alpha Vantage)
3. Multi-source local-first approach (institutional + news + optional public) ✅

**Decision**: Option 3 - Multi-source local-first sentiment analysis

**Reasoning**:
- Institutional sentiment (13F deltas) provides strongest signal for equity movements
- RSS news sentiment adds market narrative context without external dependencies
- Optional public sentiment (Reddit/X) behind flags for users who want comprehensive coverage
- Local FinBERT classification maintains our no-external-dependency principle
- Deterministic aggregation algorithm ensures auditability and reproducibility

**Implementation Notes**:
- RSS-first strategy with conditional gets (ETag/Last-Modified) for efficiency
- Local FinBERT model for financial sentiment classification (no cloud APIs)
- Strict relevance filtering (ticker mention + financial keywords)
- Near-duplicate detection with rapidfuzz to prevent spam/duplicate signal
- Optional features behind environment flags (Reddit/X require credentials)
- Integration with Enhanced MetricsJSON v2 and existing audit system

**Status**: SNT0 COMPLETED - ADR-0005 created, schemas defined, ready for implementation
**Status**: SNT1 COMPLETED - RSS ingestion pipeline with conditional gets (ETag/Last-Modified), near-duplicate detection (rapidfuzz), ticker hint extraction, relevance filtering, and comprehensive validation

## 2025-01-XX - Enhanced Sentiment Architecture (SNT1B/SNT1C)

**Goal**: Enhance sentiment analysis with Google Trends and insider trading data for comprehensive sentiment coverage

**Options Considered**:
1. News-only sentiment (current SNT1 implementation)
2. Add Google Trends for retail sentiment signals
3. Add insider trading (SEC Form 4) for insider sentiment signals
4. Add both Google Trends and insider trading ✅

**Decision**: Option 4 - Add both Google Trends and insider trading to create comprehensive 5-source sentiment analysis

**Reasoning**:
- Google Trends search interest often precedes price movements (retail sentiment leading indicator)
- Insider trading (Form 4 filings) provides strongest signal of insider confidence/concern
- Combined with existing institutional (13F deltas) and news sentiment creates comprehensive coverage
- Both sources are available locally without external API dependencies (pytrends, SEC EDGAR)
- Maintains local-first architecture while significantly enhancing sentiment signal quality

**Implementation Notes**:
- SNT1B: pytrends library for Google Trends data with rate limiting and caching
- SNT1C: SEC Form 4 scraping using existing EDGAR infrastructure with transaction pattern analysis
- Enhanced sentiment_snapshot schema with search_score, insider_score components
- Weighted composite scoring: institutional (30%), insider (25%), news (25%), search (20%)
- All sources optional and can be enabled/disabled independently

**Status**: ARCHITECTURE UPDATED - Ready to implement SNT1B (Google Trends) and SNT1C (insider trading)
**Status**: SNT1B COMPLETED - Google Trends integration with pytrends, abnormality detection (Z-scores + percentiles), search volume trend analysis, and comprehensive validation (27 tests passing)
**Status**: SNT1C COMPLETED - Insider trading integration with SEC Form 4 processing, pattern detection (clustering, consensus, large transactions), baseline calculation, and comprehensive validation (21 tests passing)

**Links**: Related to ADR-0005 Sentiment Analysis Architecture

---

*Template for future entries*:
## YYYY-MM-DD - Decision Title (Ticket ID)
**Goal**: What we're trying to achieve
**Options Considered**: List of alternatives with pros/cons
**Decision**: Chosen option with ✅
**Reasoning**: Why this option was selected
**Implementation Notes**: Key details for implementation
**Links**: References to ADRs, tickets, or related decisions
