# AI Stock Market Research Workbench

A local-first stock market research tool that generates comprehensive research reports combining quantitative metrics with AI-assisted narrative.

## Features

- **Price Analysis**: OHLCV data from yfinance with returns, volatility, and drawdown metrics
- **Institutional Holdings**: 13F filing analysis showing top holders and concentration
- **AI Narrative**: Ollama-powered executive summaries and risk descriptions
- **Data Integrity**: All calculations are deterministic and traceable
- **Local-First**: Your data stays on your machine
- **Reproducible**: Same inputs always produce same outputs

## Quick Start

### Prerequisites

- Python 3.9+
- [Ollama](https://ollama.ai/) installed and running
- 500MB free disk space

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd thats_my_quant
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment:
```bash
cp env.example .env
# Edit .env with your configuration
```

5. Pull Ollama model:
```bash
ollama pull llama2:7b
```

### Usage

Generate a research report:
```bash
python cli.py report AAPL
```

List previous runs:
```bash
python cli.py list_runs
```

Get latest report for a ticker:
```bash
python cli.py latest_report AAPL
```

## Project Structure

```
.
├── .cursor/rules/      # Cursor AI rules (MDC format)
├── analysis/           # Metrics calculation engine
├── data/              # Data storage (git-ignored)
│   ├── cache/         # Temporary API responses
│   ├── processed/     # Cleaned data files
│   └── research.db    # SQLite database
├── decisions/         # Architecture Decision Records
├── ingestion/         # Data fetching modules
├── reports/           # Generated reports (git-ignored)
├── tests/             # Test suite
│   └── fixtures/      # Golden test data
├── AGENTS.md          # AI agent instructions
├── plan.md           # Project plan and task graph
├── assumptions.md    # Technical assumptions
├── risks.md          # Risk register
└── changelog.md      # Change history
```

## Key Principles

1. **95% Confidence Gate**: Stop and ask if uncertain
2. **No Hallucinations**: All numbers from code, not AI
3. **Data Provenance**: Every metric traces to source
4. **Local-First**: No cloud dependencies for MVP
5. **Small Commits**: Atomic, well-documented changes

## Architecture

The system follows a local-first architecture where:
- All calculations are performed in Python (deterministic)
- LLM (Ollama) is used only for narrative prose
- Data is stored locally in SQLite and files
- No external dependencies beyond data APIs

See [ADR-0001](decisions/ADR-0001.md) for detailed architecture decisions.

## Development

### Running Tests
```bash
pytest tests/
```

### Code Quality
```bash
# Linting
pylint ingestion analysis

# Type checking
mypy ingestion analysis

# Coverage
pytest --cov=. --cov-report=html
```

### Contributing

1. Read [AGENTS.md](AGENTS.md) for operating principles
2. Check [plan.md](plan.md) for current tasks
3. Follow rules in `.cursor/rules/`
4. Update relevant documentation
5. Write tests for new features
6. Keep commits atomic and well-described

## Data Sources

- **Price Data**: Yahoo Finance via yfinance
- **13F Holdings**: SEC EDGAR database
- **Narrative**: Local Ollama LLM

## Security

- Never commit `.env` files
- Use environment variables for sensitive data
- All SQL queries are parameterized
- Input validation on all user data
- See [.cursor/rules/security.mdc](.cursor/rules/security.mdc)

## Troubleshooting

### Ollama not responding
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
ollama serve
```

### Rate limiting from APIs
- SEC: Max 10 requests/second
- yfinance: Automatic retry with backoff
- Check logs in `data/logs/`

### Missing data in reports
- Check data coverage in report metadata
- Review `data/logs/` for fetch errors
- May need to wait for quarterly 13F filings

## Roadmap

### Current (MVP)
- [x] Project scaffold and rules
- [ ] Basic report generation
- [ ] CLI interface
- [ ] Golden ticker tests

### Future
- [ ] News integration
- [ ] Valuation metrics
- [ ] Web interface
- [ ] Cloud sync (optional)

## License

[License Type] - See LICENSE file

## Disclaimer

This tool is for informational purposes only. Not investment advice. Always do your own research before making investment decisions.

## Support

- Check [risks.md](risks.md) for known issues
- Review [assumptions.md](assumptions.md) for limitations
- See [changelog.md](changelog.md) for recent changes

---

*Built with 95% confidence or clarifying questions asked.*
