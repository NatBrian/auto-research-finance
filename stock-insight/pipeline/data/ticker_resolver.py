"""Ticker symbol normalization and resolution."""
import re
from typing import Optional, Tuple


def normalize_ticker(ticker: str, default_suffix: str = "JK") -> Tuple[str, str]:
    """
    Normalize ticker symbol and determine market.

    Returns: (normalized_ticker, market)
    - normalized_ticker: uppercase ticker with suffix
    - market: "US", "JK", or other

    Examples:
        "aapl" -> ("AAPL.US", "US")
        "bbca.jk" -> ("BBCA.JK", "JK")
        "MSFT" -> ("MSFT.JK", "JK") if default_suffix="JK"
    """
    ticker = ticker.upper().strip()

    # Check if already has suffix
    if "." in ticker:
        symbol, suffix = ticker.split(".", 1)
        return ticker, suffix

    # Add default suffix
    return f"{ticker}.{default_suffix}", default_suffix


def resolve_yfinance_ticker(ticker: str) -> str:
    """
    Convert to yfinance-compatible ticker format.

    yfinance uses:
    - No suffix for US stocks (AAPL)
    - .JK for Jakarta stocks (BBCA.JK)
    - .BO for Bombay stocks
    """
    ticker = ticker.upper().strip()

    # US stocks: remove .US suffix for yfinance
    if ticker.endswith(".US"):
        return ticker[:-3]

    return ticker


def get_market_suffix(market: str) -> str:
    """Get yfinance suffix for market."""
    suffixes = {
        "US": "",
        "JK": ".JK",
        "BO": ".BO",
        "L": ".L",      # London
        "TO": ".TO",    # Toronto
        "PA": ".PA",    # Paris
        "DE": ".DE",    # Germany
        "HK": ".HK",    # Hong Kong
        "AX": ".AX",    # Australia
        "T": ".T",      # Tokyo
    }
    return suffixes.get(market.upper(), "")


def is_valid_ticker(ticker: str) -> bool:
    """Validate ticker format."""
    pattern = r'^[A-Z]{1,5}(\.[A-Z]{1,3})?$'
    return bool(re.match(pattern, ticker.upper()))


def extract_symbol(ticker: str) -> str:
    """Extract base symbol without suffix."""
    ticker = ticker.upper()
    if "." in ticker:
        return ticker.split(".")[0]
    return ticker