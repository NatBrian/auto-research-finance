---
name: stock-ingest
description: Fetch financial data with caching and fallback chains. Usage: /stock-ingest <TICKER>
argument-hint: <TICKER>
disable-model-invocation: true
allowed-tools: Bash(python pipeline/data/*) Read Write
---
# Data Fetching Skill

## Fallback Chain (Strict Order - implement in pipeline/data/fetchers.py)
1. Local SQLite `data/cache.db` (check TTL first)
2. `yfinance` (unlimited, rate-limited ~100 req/min)
3. `Twelve Data` (ONLY if daily quota < 700; track in `api_usage` table)
4. `Finnhub` (ONLY if minute quota < 50; track in `api_usage` table)
5. Return `None` → triggers UI tab hide in Jinja template

## SQLite Schema (pipeline/data/db.py)
```sql
CREATE TABLE IF NOT EXISTS data_cache (
    ticker TEXT NOT NULL,
    data_type TEXT NOT NULL,
    source TEXT NOT NULL,
    data_blob TEXT NOT NULL,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (ticker, data_type, source)
);
CREATE TABLE IF NOT EXISTS api_usage (
    date DATE NOT NULL,
    service TEXT NOT NULL,
    call_count INTEGER DEFAULT 0,
    PRIMARY KEY (date, service)
);
```

## Cache TTLs (pipeline/config.py constants)
- Price: 15 minutes
- News: 6 hours
- Financials/Dividends: 7 days
- Profile: 30 days

## API Mappings
### yfinance (Primary)
```python
import yfinance as yf
stock = yf.Ticker(ticker)
stock.info                    # Company profile, current price
stock.history(period='max')   # Historical OHLCV
stock.financials              # Income statement
stock.balance_sheet           # Balance sheet
stock.cashflow                # Cash flow statement
stock.dividends               # Dividend history
stock.news                    # Recent news
stock.recommendations         # Analyst ratings
stock.institutional_holders   # Institutional ownership
```

### Twelve Data Fallback
- `/time_series` → historical prices
- `/profile` → company profile
- `/income_statement` → financials
- Track calls: increment `api_usage` where service='twelvedata'

### Finnhub Fallback
- `/stock/candle` → historical prices
- `/company-news` → news articles
- Track calls: increment `api_usage` where service='finnhub'

## Error Handling
- Always wrap calls in try/except
- Log failures to stderr, not stdout
- On HTTP 429: exponential backoff (1s start, 30s max)
- Never expose API keys in logs

## Output Contract
After execution, print to stdout:
```
DATA_FETCH: ticker=$0 price=OK|MISSING financials=OK|MISSING dividends=OK|MISSING news=OK|MISSING
CACHE_HITS: <count> | API_CALLS: yfinance=<n> twelvedata=<n> finnhub=<n>
```

## Quota Management
```python
def check_quota(service: str, limit: int) -> bool:
    """Check if service has remaining quota for today."""
    today = datetime.utcnow().date()
    count = db.execute(
        "SELECT call_count FROM api_usage WHERE date=? AND service=?",
        (today, service)
    ).fetchone()
    return (count[0] if count else 0) < limit

def increment_quota(service: str):
    """Increment API call counter."""
    today = datetime.utcnow().date()
    db.execute("""
        INSERT INTO api_usage (date, service, call_count)
        VALUES (?, ?, 1)
        ON CONFLICT(date, service)
        DO UPDATE SET call_count = call_count + 1
    """, (today, service))
```