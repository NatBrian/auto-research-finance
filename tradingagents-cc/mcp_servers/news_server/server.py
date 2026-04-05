"""
TradingAgents-CC — News MCP Server

Provides tools for company news, macro news, SEC filings, and event calendar.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
from mcp.server.fastmcp import FastMCP

from src.news_fetcher import NewsFetcher
from src.utils import safe_json_dumps, setup_logging

logger = setup_logging()
mcp = FastMCP("news")
fetcher = NewsFetcher()


@mcp.tool()
def ping_news() -> str:
    """Health check for the news MCP server."""
    return json.dumps({"status": "ok", "message": "news MCP server running"})


@mcp.tool()
def search_company_news(
    ticker: str,
    date: str,
    lookback_days: int = 14,
    max_articles: int = 20,
) -> str:
    """Search for recent news articles about a company."""
    try:
        articles = fetcher.search_company_news(ticker, date, lookback_days, max_articles)
        return safe_json_dumps(articles)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def search_macro_news(
    date: str,
    lookback_days: int = 7,
    topics: str = "",
) -> str:
    """Search for macro-economic news across multiple topics.

    Pass topics as a comma-separated string, e.g. 'federal reserve,inflation,gdp'.
    If empty, uses default topic list.
    """
    try:
        topic_list = [t.strip() for t in topics.split(",") if t.strip()] if topics else None
        articles = fetcher.search_macro_news(date, lookback_days, topic_list)
        return safe_json_dumps(articles)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def get_recent_sec_filings(ticker: str, lookback_days: int = 30) -> str:
    """Fetch recent SEC filings for a company."""
    try:
        filings = fetcher.get_recent_sec_filings(ticker, lookback_days)
        return safe_json_dumps(filings)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def get_event_calendar(ticker: str, lookahead_days: int = 30) -> str:
    """Get upcoming events (earnings, dividends) for a ticker."""
    try:
        events = fetcher.get_event_calendar(ticker, lookahead_days)
        return safe_json_dumps(events)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


if __name__ == "__main__":
    logger.info("Starting News MCP server...")
    mcp.run(transport="stdio")
