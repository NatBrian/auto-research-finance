# Data Module Context

Implements the stock-ingest skill specification (see `.claude/skills/stock-ingest/SKILL.md`).

## Components
- `fetchers.py` - API client functions with fallback chain
- `db.py` - SQLite cache and quota tracker
- `ticker_resolver.py` - Ticker suffix normalization

## Fallback Order
1. SQLite cache (check TTL)
2. yfinance (primary, unlimited)
3. Twelve Data (quota-limited)
4. Finnhub (quota-limited)