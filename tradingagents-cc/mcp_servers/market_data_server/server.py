"""
TradingAgents-CC — Market Data MCP Server

Provides tools for price history, financials, valuation, earnings,
insider transactions, options flow, short interest, analyst ratings,
and technical indicator computation.
"""

import sys
from pathlib import Path

# --- Inject project root so src/ is importable ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Load .env file before any other imports
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

import json
from mcp.server.fastmcp import FastMCP

from src.market_data import MarketDataClient
from src.technical_indicators import compute_indicators, detect_chart_pattern
from src.utils import safe_json_dumps, setup_logging

logger = setup_logging()
mcp = FastMCP("market_data")
client = MarketDataClient()


# ------------------------------------------------------------------
# Health Check
# ------------------------------------------------------------------

@mcp.tool()
def ping_market_data() -> str:
    """Health check for the market data MCP server."""
    return json.dumps({"status": "ok", "message": "market_data MCP server running"})


# ------------------------------------------------------------------
# Price History
# ------------------------------------------------------------------

@mcp.tool()
def get_price_history(
    ticker: str,
    end_date: str,
    lookback_days: int = 365,
    interval: str = "1d",
) -> str:
    """Fetch OHLCV price history for a ticker."""
    try:
        df = client.get_price_history(ticker, end_date, lookback_days, interval)
        records = df.reset_index().to_dict(orient="records")
        return safe_json_dumps(records)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ------------------------------------------------------------------
# Financials
# ------------------------------------------------------------------

@mcp.tool()
def get_financials(ticker: str, date: str) -> str:
    """Fetch income statement, balance sheet, and cash flow data."""
    try:
        data = client.get_financials(ticker, date)
        return safe_json_dumps(data)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ------------------------------------------------------------------
# Valuation Metrics
# ------------------------------------------------------------------

@mcp.tool()
def get_valuation_metrics(ticker: str, date: str) -> str:
    """Fetch key valuation ratios (P/E, P/B, PEG, etc.)."""
    try:
        data = client.get_valuation_metrics(ticker, date)
        return safe_json_dumps(data)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ------------------------------------------------------------------
# Earnings History
# ------------------------------------------------------------------

@mcp.tool()
def get_earnings_history(ticker: str, n_quarters: int = 8) -> str:
    """Fetch recent quarterly earnings history."""
    try:
        data = client.get_earnings_history(ticker, n_quarters)
        return safe_json_dumps(data)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ------------------------------------------------------------------
# Insider Transactions
# ------------------------------------------------------------------

@mcp.tool()
def get_insider_transactions(ticker: str, lookback_days: int = 90) -> str:
    """Fetch insider buy/sell transactions."""
    try:
        data = client.get_insider_transactions(ticker, lookback_days)
        return safe_json_dumps(data)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ------------------------------------------------------------------
# Options Flow
# ------------------------------------------------------------------

@mcp.tool()
def get_options_flow(ticker: str, date: str) -> str:
    """Compute put/call ratio and detect unusual options activity."""
    try:
        data = client.get_options_flow(ticker, date)
        return safe_json_dumps(data)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ------------------------------------------------------------------
# Short Interest
# ------------------------------------------------------------------

@mcp.tool()
def get_short_interest(ticker: str) -> str:
    """Fetch short interest data."""
    try:
        data = client.get_short_interest(ticker)
        return safe_json_dumps(data)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ------------------------------------------------------------------
# Analyst Ratings
# ------------------------------------------------------------------

@mcp.tool()
def get_analyst_ratings(ticker: str) -> str:
    """Fetch analyst consensus and price targets."""
    try:
        data = client.get_analyst_ratings(ticker)
        return safe_json_dumps(data)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ------------------------------------------------------------------
# Technical Indicators
# ------------------------------------------------------------------

@mcp.tool()
def compute_indicators_tool(
    ticker: str,
    end_date: str,
    lookback_days: int = 365,
) -> str:
    """Fetch price history and compute all technical indicators."""
    try:
        df = client.get_price_history(ticker, end_date, lookback_days, "1d")
        indicators = compute_indicators(df)
        pattern = detect_chart_pattern(df)
        indicators["chart_pattern"] = pattern
        return safe_json_dumps(indicators)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting Market Data MCP server...")
    mcp.run(transport="stdio")
