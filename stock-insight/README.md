# Stock Report Pipeline

Generate interactive, single-file HTML financial reports for any stock ticker. 100% free (excluding Claude usage) with no server required.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Generate report
python pipeline/generate_report.py --ticker AAPL

# Advanced mode with technical analysis
python pipeline/generate_report.py --ticker AAPL --mode advanced
```

## Features

- **7 Report Tabs**: Overview, Valuation, Financials, Analyst Ratings, Dividends, Ownership, News
- **Interactive Charts**: Plotly-powered candlestick, technical indicators, revenue, and more
- **Dark Mode**: Automatic theme detection with manual toggle
- **Mobile-Friendly**: Responsive design with sticky table columns
- **Offline Capable**: All assets from CDNs, no server needed
- **Free Data Sources**: yfinance (primary), Twelve Data, Finnhub (fallbacks)

## Architecture

```
stock-report-pipeline/
├── .claude/skills/           # Claude Code Skills
│   ├── stock-report/         # Orchestrator skill
│   ├── stock-ingest/         # Data fetching skill
│   ├── stock-analyze/        # Metric computation skill
│   └── stock-compile/        # Chart rendering skill
├── pipeline/                 # Python implementation
│   ├── generate_report.py    # Entry point
│   ├── config.py             # Configuration
│   ├── data/                 # Data fetching
│   ├── analyze/              # Metric calculations
│   └── compile/              # Chart generation
├── template/                 # Jinja2 templates
│   ├── report.html.jinja2    # Main template
│   ├── tabs/                 # Tab templates
│   └── components/           # Reusable components
├── data/                     # SQLite cache
└── output/                   # Generated reports
```

## Claude Code Skills

Invoke via slash commands:

- `/stock-report AAPL` - Generate beginner report
- `/stock-report AAPL advanced` - Generate advanced report with technical analysis
- `/stock-ingest AAPL` - Fetch data only
- `/stock-analyze AAPL` - Compute metrics only
- `/stock-compile AAPL` - Generate charts only

## Configuration

Copy `.env.example` to `.env` and add your API keys:

```bash
cp .env.example .env
```

| Source | Free Tier | Key Required |
|--------|-----------|--------------|
| yfinance | Unlimited | No |
| Twelve Data | 800/day | Yes |
| Finnhub | 60/min | Yes |

## Output

Reports are saved to `output/{TICKER}_{YYYY-MM-DD}.html`:

- Single HTML file, no external dependencies
- Works offline after initial load
- Mobile-responsive with dark mode support

## License

MIT