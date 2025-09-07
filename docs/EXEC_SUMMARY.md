# Executive Summary Contract (Quantitative-Only)

## Overview

The executive summary provides a 120-180 word paragraph synthesizing quantitative price and ownership metrics. No sentiment analysis or external context - only verified data from MetricsJSON.

## Input Contract

**Source**: Complete MetricsJSON from analysis engine
**Required Fields**: `price_metrics`, `institutional_metrics` (optional), `as_of_date`

## Output Contract

**Format**: Single paragraph, 120-180 words
**Tone**: Neutral, factual, professional
**Content**: Must mention (if available):
1. Most recent volatility with window
2. Largest drawdown with dates and recovery status
3. Institutional concentration level with basis

## Formatting Rules

### Numbers
- **Percentages**: 1 decimal place (28.4%, not 28.45%)
- **Dates**: Month D, YYYY format (July 15, 2025)
- **Windows**: Parenthetical style (21-day)
- **Missing data**: "Not available" phrase

### Concentration Classification
**Prefer CR5**, fallback to HHI if CR5 missing:

**CR5 Thresholds**:
- `< 0.25` = "low concentration"
- `0.25 - 0.40` = "moderate concentration"  
- `> 0.40` = "high concentration"

**HHI Thresholds** (fallback):
- `< 0.10` = "low concentration"
- `0.10 - 0.18` = "moderate concentration"
- `> 0.18` = "high concentration"

**Always specify basis**: "based on CR5" or "based on HHI"

### Drawdown Wording
- **If recovery_date exists**: "recovered by {Month D, YYYY}"
- **If recovery_date is null**: "unrecovered as of {as_of_date}"

## Anti-Hallucination Strategy

### Data-Stitched Approach (Primary)
1. **Skeleton Builder**: Code pre-fills all numbers/dates from METRICS
2. **LLM Polish**: "Improve readability without changing any values"
3. **Number Audit**: Verify 1:1 correspondence with source data
4. **Fallback**: Use unpolished skeleton if audit fails

### Prompt Contracts

**System Prompt** (constant):
```
You are a neutral equity research analyst. Use ONLY the provided data. Do not invent numbers or dates. No recommendations or price targets. If a field is missing, write "Not available." Keep to one paragraph (120-180 words).
```

**Developer Prompt** (constant):
```
You will receive (A) a DRAFT paragraph that already contains all numbers and dates pulled from METRICS, and (B) the raw METRICS JSON. Edit the DRAFT for clarity and flow without altering any numbers or dates and without adding new ones.
```

**User Prompt** (per call):
```
Improve the DRAFT summary for readability. Keep one paragraph (120-180 words). Do not change any numeric values or dates; do not add any new figures.
```

## Example Skeleton (Before LLM Polish)

```
AAPL demonstrated returns of 2.3% (1-day) and 8.9% (1-month) with volatility of 28.4% (21-day). The stock experienced a maximum drawdown of -18.5% from July 15, 2025 to August 12, 2025, recovering by August 28, 2025. Institutional ownership shows moderate concentration based on CR5 with top 5 holders controlling 12.3% of 13F value across 145 institutions totaling $125.0B. Current price stands at $229.87 as of September 5, 2025. Trading data covers 252 days with 98.5% coverage. 13F data reflects September 30, 2024 quarter (45 days old).
```

## Example Polished Output

```
Apple Inc. (AAPL) has shown strong recent momentum with a 1-month return of 8.9% despite experiencing moderate volatility of 28.4% over the 21-day period. While the stock faced a significant drawdown of -18.5% from its July 15, 2025 peak to the August 12, 2025 trough, it successfully recovered by August 28, 2025, demonstrating resilience. The institutional ownership landscape reveals moderate concentration based on CR5, with the top 5 holders controlling 12.3% of the total $125.0B in 13F value across 145 reporting institutions. At the current price of $229.87 (September 5, 2025), the analysis draws from 252 trading days with 98.5% data coverage, while institutional holdings reflect the September 30, 2024 reporting quarter.
```

## Failure Handling

### Missing Data Phrases
- **Volatility missing**: "Volatility data not available"
- **Drawdown missing**: "Drawdown analysis not available" 
- **13F missing**: "Institutional ownership data not available"
- **Insufficient price data**: "Limited price history available"

### Audit Failure Response
1. **First failure**: Log warning, retry LLM with stricter prompt
2. **Second failure**: Use unpolished skeleton, log error
3. **Never ship**: Paragraphs with hallucinated numbers

### Length Enforcement
- **< 120 words**: Expand with available data context
- **> 180 words**: Truncate at sentence boundary near 180
- **Target**: 140-160 words for optimal readability

## Quality Metrics

### Success Criteria
- ✅ All numbers traceable to MetricsJSON
- ✅ All dates from source data
- ✅ Word count within bounds
- ✅ Mentions required elements (volatility, drawdown, concentration)
- ✅ Professional tone and flow

### Validation Rules
- **Number audit pass rate**: >95%
- **Word count compliance**: 100%
- **Required elements coverage**: 100% when data available
- **Fallback rate**: <5% (LLM should rarely fail audit)
