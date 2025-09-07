# Ticker Symbol Management

This document describes how ticker symbols are managed and validated in the AI Stock Market Research Workbench.

## Overview

The system uses the [US-Stock-Symbols](https://github.com/rreichel3/US-Stock-Symbols) repository to provide comprehensive ticker symbol mapping and validation for NASDAQ, NYSE, and AMEX exchanges.

## Data Source

- **Repository**: US-Stock-Symbols (included as `US-Stock-Symbols-main/`)
- **Update Frequency**: Nightly at midnight Eastern
- **Coverage**: 6,600+ symbols across 3 major US exchanges
- **Exchanges**: NASDAQ (3,984), NYSE (2,378), AMEX (280)

## File Structure

```
US-Stock-Symbols-main/
├── all/
│   └── all_tickers.txt          # All symbols (may have duplicates across exchanges)
├── nasdaq/
│   ├── nasdaq_tickers.txt       # NASDAQ symbols only
│   ├── nasdaq_tickers.json      # NASDAQ symbols as JSON array
│   └── nasdaq_full_tickers.json # Full NASDAQ data with company details
├── nyse/
│   ├── nyse_tickers.txt
│   ├── nyse_tickers.json
│   └── nyse_full_tickers.json
└── amex/
    ├── amex_tickers.txt
    ├── amex_tickers.json
    └── amex_full_tickers.json
```

## Usage

### Command Line Utility

```bash
# Get ticker statistics
python utils/list_tickers.py stats

# List all tickers (warning: 6000+ symbols)
python utils/list_tickers.py all

# List tickers for specific exchange
python utils/list_tickers.py exchange nasdaq
python utils/list_tickers.py exchange nyse
python utils/list_tickers.py exchange amex

# Get details for specific ticker
python utils/list_tickers.py lookup TSLA

# Validate ticker symbol
python utils/list_tickers.py validate AAPL
```

### Programmatic Usage

```python
from utils.list_tickers import get_all_tickers, is_valid_ticker, get_ticker_details

# Get all available tickers
all_tickers = get_all_tickers()  # Returns set of 6,600+ symbols

# Validate a ticker
if is_valid_ticker("TSLA"):
    print("TSLA is valid")

# Get ticker details
details = get_ticker_details("TSLA")
if details:
    print(f"Company: {details['name']}")
    print(f"Exchange: {details['exchange']}")
    print(f"Sector: {details['sector']}")
```

## 13F Ticker Mapping

The system uses comprehensive ticker mapping for 13F institutional holdings:

### Mapping Process

1. **Primary Mapping**: Uses `ingestion/transforms/ticker_mapper.py`
2. **Data Source**: US-Stock-Symbols full ticker JSON files
3. **Mapping Strategy**: 
   - Exact name matching
   - Normalized name matching (removes common suffixes)
   - Fuzzy matching for similar company names

### Common Name Transformations

The system automatically handles these transformations:

- `"Tesla Inc. Common Stock"` → `"TESLA"` → `"TSLA"`
- `"Apple Inc. Common Stock"` → `"APPLE"` → `"AAPL"`
- `"Microsoft Corporation Common Stock"` → `"MICROSOFT"` → `"MSFT"`
- `"Amazon.com Inc. Common Stock"` → `"AMAZON COM"` → `"AMZN"`

### Mapping Statistics

- **Total Mappings**: 6,999 ticker symbols
- **Name Mappings**: 11,800+ company name variations
- **Success Rate**: ~95% for major institutional holdings

## Validation and Quality

### Data Quality Checks

- **Completeness**: All exchanges covered
- **Freshness**: Updated nightly from source
- **Consistency**: Standardized formats across exchanges

### Error Handling

- **Invalid Tickers**: Return "UNKNOWN" for unmapped companies
- **Missing Data**: Graceful fallback to best-effort matching
- **File Errors**: Clear error messages with fallback strategies

## Integration Points

### Analysis Engine

The analysis engine uses ticker validation when:
- Processing 13F holdings data
- Validating user input for reports
- Cross-referencing price data with institutional holdings

### Report Generation

Reports include ticker validation status:
- Valid tickers show full company details
- Invalid/unknown tickers are clearly marked
- Data quality metrics include ticker mapping success rates

## Future Enhancements

### Planned Improvements

1. **Enhanced Fuzzy Matching**: Better algorithm for company name variations
2. **Historical Ticker Mapping**: Handle ticker changes over time
3. **International Exchanges**: Expand beyond US markets
4. **Real-time Updates**: Automatic sync with upstream repository

### Known Limitations

- **US Markets Only**: No international exchange coverage
- **Static Mapping**: No real-time ticker change detection
- **Name Variations**: Some obscure company name formats may not map correctly

## Troubleshooting

### Common Issues

**Issue**: Ticker shows as "UNKNOWN" in 13F data
**Solution**: Check if company name exists in mapping with `python utils/list_tickers.py lookup TICKER`

**Issue**: FileNotFoundError for US-Stock-Symbols data
**Solution**: Ensure `US-Stock-Symbols-main/` directory exists in project root

**Issue**: Ticker validation fails
**Solution**: Verify ticker exists with `python utils/list_tickers.py validate TICKER`

### Debug Commands

```bash
# Check mapping statistics
python -c "from ingestion.transforms.ticker_mapper import ticker_mapper; print(ticker_mapper.get_stats())"

# Test specific company mapping
python -c "from ingestion.transforms.ticker_mapper import ticker_mapper; print(ticker_mapper.get_ticker('TESLA INC'))"

# List unknown tickers in database
python -c "
import sqlite3
conn = sqlite3.connect('data/research.db')
cursor = conn.execute('SELECT COUNT(*) FROM holdings_13f WHERE ticker = \"UNKNOWN\"')
print(f'Unknown tickers: {cursor.fetchone()[0]}')
"
```
