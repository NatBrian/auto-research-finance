# Stock Report Pipeline

Generate interactive, single-file HTML financial reports for any stock ticker. 100% free with no server required.

---

## 1. Overview

This pipeline generates professional financial reports as standalone HTML files. It fetches data from free APIs, computes financial metrics, renders interactive charts, and outputs a polished report.

### Key Features

- **7 Report Tabs**: Overview, Valuation, Financials, Analyst Ratings, Dividends, Ownership, News
- **Interactive Charts**: Plotly-powered candlestick, technical indicators, revenue, and more
- **Dark Mode**: Automatic theme detection with manual toggle
- **Mobile-Friendly**: Responsive design with sticky table columns
- **Offline Capable**: All assets from CDNs, no server needed
- **Free Data Sources**: yfinance (primary), Twelve Data, Finnhub (fallbacks)
- **Two Modes**: Beginner (simplified) and Advanced (technical analysis)

---

## 2. Quick Start

### 2.1 Install Dependencies

```bash
pip install -r requirements.txt
```

### 2.2 Generate Report

```bash
# Beginner mode (default)
python pipeline/generate_report.py --ticker AAPL

# Advanced mode with technical analysis
python pipeline/generate_report.py --ticker AAPL --mode advanced

# Force refresh data (ignore cache)
python pipeline/generate_report.py --ticker AAPL --force-refresh
```

### 2.3 Using Claude Code Skills

```bash
# In Claude Code session
/stock-report AAPL              # Beginner report
/stock-report AAPL advanced     # Advanced report
```

---

## 3. Architecture

```
stock-insight/
├── .claude/skills/           # Claude Code Skills
│   ├── stock-report/         # Orchestrator skill
│   ├── stock-ingest/         # Data fetching skill
│   ├── stock-analyze/        # Metric computation skill
│   └── stock-compile/        # Chart rendering skill
├── pipeline/                 # Python implementation
│   ├── generate_report.py    # Entry point
│   ├── config.py             # Configuration & paths
│   ├── data/                 # Data fetching
│   │   ├── fetchers.py       # API clients with fallback chain
│   │   ├── db.py             # SQLite cache & quota tracking
│   │   └── ticker_resolver.py # Ticker normalization
│   ├── analyze/              # Metric calculations
│   │   └── calculators.py    # Financial formulas
│   └── compile/              # Chart generation
│       └── chart_renderer.py # Plotly figures
├── template/                 # Jinja2 templates
│   ├── report.html.jinja2    # Main layout
│   ├── tabs/                 # Tab content templates
│   │   ├── overview.html.jinja2
│   │   ├── valuation.html.jinja2
│   │   ├── financials.html.jinja2
│   │   ├── analyst.html.jinja2
│   │   ├── dividends.html.jinja2
│   │   ├── ownership.html.jinja2
│   │   └── news.html.jinja2
│   └── components/           # Reusable components
│       ├── metric_card.html.jinja2
│       ├── chart_container.html.jinja2
│       └── data_table.html.jinja2
├── data/                     # SQLite cache
│   └── cache.db              # Auto-created
├── output/                   # Generated reports
│   └── {TICKER}_{DATE}.html
├── requirements.txt
├── .env.example
└── README.md
```

---

## 4. Skills Reference

The pipeline consists of 4 Claude Code skills. One orchestrator coordinates the workflow, while 3 individual skills handle specific tasks.

### Skill Overview

| Skill | Purpose | Trigger Phrases |
|-------|---------|-----------------|
| **stock-report** | Main orchestrator - generates full report | "generate report", "stock report" |
| **stock-ingest** | Fetch data with caching | "fetch data", "ingest data" |
| **stock-analyze** | Compute financial metrics | "analyze stock", "compute metrics" |
| **stock-compile** | Generate Plotly charts | "compile charts", "render charts" |

---

### stock-report (Orchestrator)

Runs the full pipeline from data fetch to HTML generation.

```
/stock-report AAPL
/stock-report AAPL advanced
```

**Execution Sequence:**
1. Validate ticker format (e.g., AAPL, BBCA.JK, MSFT.US)
2. Invoke `stock-ingest` to fetch data
3. Invoke `stock-analyze` to compute metrics
4. Invoke `stock-compile` to generate charts
5. Run `pipeline/generate_report.py`
6. Parse output and present HTML file

---

### stock-ingest (Data Fetching)

Fetches financial data with a fallback chain.

```
/stock-ingest AAPL
```

**Fallback Chain:**
1. SQLite cache (check TTL first)
2. yfinance (unlimited, ~100 req/min)
3. Twelve Data (if daily quota < 700)
4. Finnhub (if minute quota < 50)
5. Return None → UI hides that tab

**Cache TTLs:**
| Data Type | TTL |
|-----------|-----|
| Price | 15 minutes |
| News | 6 hours |
| Financials | 7 days |
| Dividends | 7 days |
| Profile | 30 days |

---

### stock-analyze (Metric Computation)

Computes financial metrics with validation.

```
/stock-analyze AAPL --mode advanced
```

**Metric Categories:**

| Category | Metrics |
|----------|---------|
| Profitability | ROE, ROA, Net Margin, Gross Margin |
| Leverage | Debt/Equity, Debt/Assets |
| Valuation | P/E, P/B, P/S, P/CF, PEG, EV/EBITDA |
| Dividend | Yield, Payout Ratio, 5Y CAGR |
| Growth | Revenue YoY, Net Income YoY |
| Technical* | RSI, SMA 20/50/200, MACD, Bollinger Bands |

*Technical metrics only in advanced mode.

**Validation Thresholds:**
- RSI: requires ≥14 price rows
- Bollinger Bands: requires ≥30 rows
- SMA 200: requires ≥200 rows
- YoY Growth: requires ≥4 quarters

---

### stock-compile (Chart Generation)

Generates Plotly charts for the report.

```
/stock-compile AAPL --mode advanced
```

**Chart Types:**

| Chart | Description | Mode |
|-------|-------------|------|
| Price | Candlestick + Volume + SMAs | Both |
| Technical | RSI + MACD + Bollinger | Advanced only |
| Revenue | Bar + Line combo | Both |
| Dividend | Annual dividend bars | Both |
| Ownership | Institutional pie chart | Both |
| Performance | Period returns bars | Both |

---

## 5. Configuration

### 5.1 Environment Variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Description | Required |
|----------|-------------|----------|
| `TWELVEDATA_API_KEY` | Twelve Data API key | No |
| `FINNHUB_API_KEY` | Finnhub API key | No |
| `SSL_VERIFY` | Disable SSL for proxies (default: true) | No |
| `DEFAULT_SUFFIX` | Default ticker suffix (default: JK) | No |
| `DEFAULT_MODE` | Default report mode (default: beginner) | No |

### 5.2 API Quotas (Free Tier)

| Source | Free Tier | Key Required |
|--------|-----------|--------------|
| yfinance | Unlimited | No |
| Twelve Data | 800/day | Yes |
| Finnhub | 60/min | Yes |

---

## 6. Output

### Report File

Reports are saved to `output/{TICKER}_{YYYY-MM-DD}.html`:

- Single HTML file, no external dependencies
- Works offline after initial load
- Mobile-responsive with dark mode support
- All charts rendered client-side via Plotly.js

### Stdout Contract

The script prints structured output:

```
OUTPUT: output/AAPL_2026-04-08.html
QUALITY: price=OK financials=OK dividends=OK news=OK analyst=MISSING ownership=OK
SECTIONS: overview,valuation,financials,dividends,ownership,news
WARNINGS: Analyst data unavailable
```

---

## 7. Mode Differences

### Beginner Mode (Default)

- Simplified metric labels with tooltips
- No technical indicators
- Limited table rows (5 per section)
- Focus on fundamental metrics

### Advanced Mode

- Abbreviated labels (P/E, P/B, etc.)
- Full technical analysis (RSI, MACD, Bollinger)
- All table rows with pagination
- Additional valuation metrics (PEG, EV/EBITDA)

---

## 8. Ticker Format

Supported formats:

| Format | Example | Description |
|--------|---------|-------------|
| US Stock | `AAPL`, `MSFT` | US exchanges |
| US with suffix | `AAPL.US` | Explicit US |
| Indonesian | `BBCA.JK` | Jakarta Stock Exchange |

Validation pattern: `^[A-Z]{1,5}(\.(JK|US))?$`

---

## 9. Data Flow

```
User Request
     │
     ▼
┌─────────────────┐
│  stock-report   │  (Orchestrator)
└────────┬────────┘
         │
    ┌────┴────┬─────────┬─────────┐
    ▼         ▼         ▼         ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌─────────────┐
│ingest │ │analyze│ │compile│ │generate_    │
│       │ │       │ │       │ │report.py    │
└───┬───┘ └───┬───┘ └───┬───┘ └──────┬──────┘
    │         │         │            │
    ▼         ▼         ▼            ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌─────────────┐
│Cache/ │ │Metrics│ │Charts │ │ HTML Report │
│ APIs  │ │ Dict  │ │ JSON  │ │   Output    │
└───────┘ └───────┘ └───────┘ └─────────────┘
```

**Key Points:**
- Data flows through Python dicts in memory (no intermediate files)
- SQLite cache persists between runs
- Charts are Plotly JSON rendered client-side
- Templates use Jinja2 with autoescape

---

## 10. Extending the Pipeline

### Adding New Metrics

Edit `pipeline/analyze/calculators.py`:

```python
def calculate_my_metric(data: Dict) -> Optional[float]:
    """Calculate custom metric."""
    value = data.get("some_field")
    if value is None:
        return None
    return round_metric(value * 100, 1)
```

### Adding New Charts

Edit `pipeline/compile/chart_renderer.py`:

```python
def create_my_chart(data: Dict) -> Optional[Dict]:
    """Create custom chart."""
    fig = go.Figure()
    # Add traces...
    return {"json": fig.to_json()}
```

### Adding New Templates

Create `template/tabs/my_tab.html.jinja2` and add to `REPORT_SECTIONS` in `config.py`.

---

## 11. Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| "Price data unavailable" | Check internet connection; ticker may be delisted |
| "SSL certificate verify failed" | Set `SSL_VERIFY=false` in `.env` |
| Empty report | Try `--force-refresh` to bypass cache |
| Import error | Run `pip install -r requirements.txt` |

### Debug Mode

Run with verbose output:

```bash
python pipeline/generate_report.py --ticker AAPL 2>&1 | tee debug.log
```