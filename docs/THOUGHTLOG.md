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

*Template for future entries*:
## YYYY-MM-DD - Decision Title (Ticket ID)
**Goal**: What we're trying to achieve
**Options Considered**: List of alternatives with pros/cons
**Decision**: Chosen option with ✅
**Reasoning**: Why this option was selected
**Implementation Notes**: Key details for implementation
**Links**: References to ADRs, tickets, or related decisions
