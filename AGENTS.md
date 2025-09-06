# AI Agent Operating Instructions

## Mission
You are building a **local-first AI Stock Market Research Workbench** that generates data-driven research reports using deterministic calculations and LLM-assisted narrative.

## Core Operating Principles

### 1. Confidence Gate (95% Rule)
- **STOP** if confidence < 95% for any operation
- Ask clarifying questions rather than assume
- Break complex tasks into verifiable steps
- Never proceed with uncertainty

### 2. Data Integrity
- All calculations in code, never in prose
- Missing data → "Not available" (never interpolate)
- Every data point needs source + timestamp
- Maintain full audit trail

### 3. Planning Discipline
- Read `plan.md` before starting any task
- Update planning docs with each significant step
- Run pre-mortem analysis (3 failure modes)
- Document decisions in `changelog.md`

### 4. Git Hygiene
- Atomic commits (one logical change)
- Format: `type(scope): summary`
- Maximum 50 lines per commit
- Never commit secrets or sensitive data

### 5. Security First
- Use environment variables for secrets
- Create `.env.example` as template
- Validate all user inputs
- Parameterized SQL queries only

### 6. Testing Standards
- Snapshot tests for reports
- Deterministic test data
- Validate before LLM calls
- 100% coverage on critical paths

### 7. LLM Boundaries
- LLM for narrative prose ONLY
- Never let LLM calculate or estimate
- Validate LLM output for hallucinations
- Enforce word limits strictly

## When Rules Apply

| Rule Set | When Active | Key Focus |
|----------|------------|-----------|
| `core.mdc` | ALWAYS | 95% confidence gate, no hallucinations |
| `planning.mdc` | ALWAYS | Update plan.md, track progress |
| `git.mdc` | On commits | Small diffs, clear messages |
| `testing.mdc` | tests/**, *test* | Snapshot tests, deterministic data |
| `security.mdc` | ALWAYS | No secrets in repo, input validation |
| `data.mdc` | ingestion/**, analysis/** | Schemas, validation, provenance |
| `reporting.mdc` | reports/** | Markdown first, LLM prose only |

## Execution Loop

```
1. READ → Load rules and plan.md
2. THINK → Check 95% confidence
3. ACT → Smallest possible change
4. CHECK → Validate outputs
5. COMMIT → Small, labeled commit
```

## Decision Framework

When facing choices:
1. Document options in `decisions/`
2. List trade-offs explicitly
3. Choose simplest solution that works
4. Update `assumptions.md` if needed

## Communication Style

- Be explicit about confidence level
- Flag uncertainties immediately
- Explain "why" in comments
- Request review on complex logic
- Never hide errors or warnings

## Red Flags (Stop Immediately)

- 🚨 Confidence below 95%
- 🚨 Missing critical data
- 🚨 Hardcoded secrets detected
- 🚨 Test failures in critical path
- 🚨 Scope creep beyond plan.md
- 🚨 LLM generating numbers
- 🚨 Unvalidated user input

## Success Criteria

- ✅ Every run is reproducible
- ✅ All data has provenance
- ✅ Reports traceable to sources
- ✅ Clean git history
- ✅ No hallucinated information
- ✅ User controls all data

## Remember

**When in doubt, stop and ask.** Better to clarify than to assume and build on incorrect foundations.
