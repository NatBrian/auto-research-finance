"""
TradingAgents-CC — Sentiment MCP Server

Provides tools for social sentiment analysis and text sentiment scoring.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
from mcp.server.fastmcp import FastMCP

from src.sentiment_engine import SentimentEngine
from src.utils import safe_json_dumps, setup_logging

logger = setup_logging()
mcp = FastMCP("sentiment")
engine = SentimentEngine()


@mcp.tool()
def ping_sentiment() -> str:
    """Health check for the sentiment MCP server."""
    return json.dumps({"status": "ok", "message": "sentiment MCP server running"})


@mcp.tool()
def get_social_sentiment(
    ticker: str,
    date: str,
    lookback_days: int = 7,
) -> str:
    """Aggregate social media sentiment for a ticker."""
    try:
        data = engine.get_social_sentiment(ticker, date, lookback_days)
        return safe_json_dumps(data)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def get_combined_sentiment(text: str) -> str:
    """Score a text snippet using VADER and TextBlob."""
    try:
        data = engine.compute_text_sentiment(text)
        return safe_json_dumps(data)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


if __name__ == "__main__":
    logger.info("Starting Sentiment MCP server...")
    mcp.run(transport="stdio")
