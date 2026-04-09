"""Data fetching with fallback chain implementation."""
import json
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf

from pipeline.config import (
    TWELVEDATA_API_KEY, FINNHUB_API_KEY, CACHE_TTL
)
from pipeline.config import SSL_VERIFY
from pipeline.data.db import (
    get_cached_data, set_cached_data,
    check_quota, increment_quota, get_cache_stats
)
from pipeline.data.ticker_resolver import resolve_yfinance_ticker


# Track API calls for reporting
api_calls = {"yfinance": 0, "twelvedata": 0, "finnhub": 0}


def exponential_backoff(attempt: int, base: float = 1.0, max_wait: float = 30.0) -> float:
    """Calculate exponential backoff wait time."""
    return min(base * (2 ** attempt), max_wait)


def fetch_with_cache(
    ticker: str,
    data_type: str,
    fetch_func,
    source: str = "yfinance",
    force_refresh: bool = False
) -> Tuple[Optional[Any], str]:
    """
    Fetch data with cache lookup and storage.

    Returns: (data, source_used)
    """
    if not force_refresh:
        cached = get_cached_data(ticker, data_type, source)
        if cached is not None:
            return cached, f"cache_{source}"

    try:
        data = fetch_func()
        if data:
            set_cached_data(ticker, data_type, data, source)
            return data, source
    except Exception as e:
        print(f"Warning: {source} fetch failed for {data_type}: {e}", file=sys.stderr)

    return None, source


def fetch_yfinance_price(stock: yf.Ticker) -> Optional[Dict]:
    """Fetch price data from yfinance."""
    try:
        info = stock.info
        hist = stock.history(period="max")

        if hist.empty:
            return None

        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")

        # Calculate change
        change = None
        change_pct = None
        if current_price and prev_close:
            change = current_price - prev_close
            change_pct = (change / prev_close) * 100

        # Drop rows with NaN values in essential columns
        hist_clean = hist.dropna(subset=['Open', 'High', 'Low', 'Close'])

        # Convert history to serializable format
        hist_df = hist_clean.reset_index()
        # Convert Date column to string if it's a Timestamp
        if 'Date' in hist_df.columns:
            hist_df['Date'] = hist_df['Date'].astype(str)
        elif 'index' in hist_df.columns:
            hist_df['index'] = hist_df['index'].astype(str)

        # Select only essential columns and drop any remaining NaN
        essential_cols = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume']
        available_cols = [c for c in essential_cols if c in hist_df.columns]
        hist_df = hist_df[available_cols]

        # Replace any remaining NaN with None for JSON serialization
        hist_df = hist_df.where(pd.notna(hist_df), None)

        history = hist_df.to_dict(orient="records")

        # Filter out records with None values in essential fields
        history = [h for h in history if all(h.get(c) is not None for c in ['Open', 'High', 'Low', 'Close'])]

        return {
            "current_price": current_price,
            "previous_close": prev_close,
            "change": change,
            "change_pct": change_pct,
            "volume": info.get("volume") or info.get("regularMarketVolume"),
            "avg_volume": info.get("averageVolume"),
            "market_cap": info.get("marketCap"),
            "high_52w": info.get("fiftyTwoWeekHigh"),
            "low_52w": info.get("fiftyTwoWeekLow"),
            "open": info.get("open") or info.get("regularMarketOpen"),
            "high": info.get("dayHigh") or info.get("regularMarketDayHigh"),
            "low": info.get("dayLow") or info.get("regularMarketDayLow"),
            "history": history,
        }
    except Exception as e:
        print(f"yfinance price fetch error: {e}", file=sys.stderr)
        return None


def fetch_yfinance_profile(stock: yf.Ticker) -> Optional[Dict]:
    """Fetch company profile from yfinance."""
    try:
        info = stock.info
        return {
            "name": info.get("longName") or info.get("shortName"),
            "symbol": info.get("symbol"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "exchange": info.get("exchange"),
            "website": info.get("website"),
            "employees": info.get("fullTimeEmployees"),
            "description": info.get("longBusinessSummary"),
            "logo_url": info.get("logo_url"),
        }
    except Exception as e:
        print(f"yfinance profile fetch error: {e}", file=sys.stderr)
        return None


def convert_df_to_serializable(df):
    """Convert DataFrame to serializable dict, handling Timestamps.

    yfinance returns financials with dates as columns, but our template expects
    dates as rows. We transpose the DataFrame.
    """
    if df.empty:
        return []

    # Transpose so dates become rows and metrics become columns
    df_transposed = df.T.reset_index()
    df_transposed.columns = ['Date'] + list(df.index)

    # Convert Date column to string
    if 'Date' in df_transposed.columns:
        df_transposed['Date'] = df_transposed['Date'].astype(str)

    # Replace NaN with None for JSON serialization
    df_transposed = df_transposed.where(pd.notna(df_transposed), None)

    return df_transposed.to_dict(orient="records")


def fetch_yfinance_financials(stock: yf.Ticker) -> Optional[Dict]:
    """Fetch financial statements from yfinance."""
    try:
        income_stmt = stock.financials
        balance_sheet = stock.balance_sheet
        cashflow = stock.cashflow

        if income_stmt.empty:
            return None

        # Get info values, with fallbacks to balance sheet
        info = stock.info

        # Try to get from info first, then from balance sheet
        total_assets = info.get("totalAssets")
        total_equity = info.get("totalStockholderEquity")

        if total_assets is None and not balance_sheet.empty:
            # Try to get from balance sheet
            if "Total Assets" in balance_sheet.index:
                total_assets = balance_sheet.loc["Total Assets"].iloc[0]
            elif "Assets" in balance_sheet.index:
                total_assets = balance_sheet.loc["Assets"].iloc[0]

        if total_equity is None and not balance_sheet.empty:
            if "Total Stockholder Equity" in balance_sheet.index:
                total_equity = balance_sheet.loc["Total Stockholder Equity"].iloc[0]
            elif "Stockholders Equity" in balance_sheet.index:
                total_equity = balance_sheet.loc["Stockholders Equity"].iloc[0]
            elif "Total Equity" in balance_sheet.index:
                total_equity = balance_sheet.loc["Total Equity"].iloc[0]

        return {
            "income_statement": convert_df_to_serializable(income_stmt),
            "balance_sheet": convert_df_to_serializable(balance_sheet),
            "cashflow": convert_df_to_serializable(cashflow),
            "info": {
                "total_revenue": info.get("totalRevenue"),
                "net_income": info.get("netIncomeToCommon"),
                "total_assets": total_assets,
                "total_equity": total_equity,
                "total_debt": info.get("totalDebt"),
                "operating_cashflow": info.get("operatingCashflow"),
                "free_cashflow": info.get("freeCashflow"),
                "ebitda": info.get("ebitda"),
                "gross_profits": info.get("grossProfits"),
            }
        }
    except Exception as e:
        print(f"yfinance financials fetch error: {e}", file=sys.stderr)
        return None


def fetch_yfinance_dividends(stock: yf.Ticker) -> Optional[Dict]:
    """Fetch dividend data from yfinance."""
    try:
        dividends = stock.dividends
        if dividends.empty:
            return None

        # Convert to list of dicts
        div_history = []
        for date, amount in dividends.items():
            div_history.append({
                "date": date.strftime("%Y-%m-%d"),
                "amount": float(amount)
            })

        # Calculate TTM dividend
        one_year_ago = datetime.now() - timedelta(days=365)
        ttm_dividend = sum(
            d["amount"] for d in div_history
            if datetime.strptime(d["date"], "%Y-%m-%d") > one_year_ago
        )

        return {
            "history": div_history[-20:],  # Last 20 dividends
            "ttm_dividend": ttm_dividend,
            "total_dividends": len(div_history),
        }
    except Exception as e:
        print(f"yfinance dividends fetch error: {e}", file=sys.stderr)
        return None


def fetch_yfinance_news(stock: yf.Ticker) -> Optional[List[Dict]]:
    """Fetch news from yfinance."""
    try:
        news = stock.news
        if not news:
            return None

        formatted_news = []
        for item in news[:20]:  # Limit to 20 articles
            # yfinance news can be a dict or object with different structures
            if isinstance(item, dict):
                formatted_news.append({
                    "title": item.get("title") or item.get("headline", ""),
                    "publisher": item.get("publisher") or item.get("source", ""),
                    "link": item.get("link") or item.get("url", ""),
                    "published": item.get("providerPublishTime") or item.get("pubDate", ""),
                    "type": item.get("type", "article"),
                    "thumbnail": item.get("thumbnail", {}).get("resolutions", [{}])[0].get("url") if isinstance(item.get("thumbnail"), dict) else None,
                })
            else:
                # Handle object-style news items
                formatted_news.append({
                    "title": getattr(item, "title", "") or getattr(item, "headline", ""),
                    "publisher": getattr(item, "publisher", "") or getattr(item, "source", ""),
                    "link": getattr(item, "link", "") or getattr(item, "url", ""),
                    "published": getattr(item, "providerPublishTime", "") or getattr(item, "pubDate", ""),
                    "type": getattr(item, "type", "article"),
                    "thumbnail": None,
                })

        return formatted_news if formatted_news else None
    except Exception as e:
        print(f"yfinance news fetch error: {e}", file=sys.stderr)
        return None


def fetch_yfinance_analyst(stock: yf.Ticker) -> Optional[Dict]:
    """Fetch analyst recommendations from yfinance."""
    try:
        recommendations = stock.recommendations
        if recommendations is None or (hasattr(recommendations, 'empty') and recommendations.empty):
            return None

        # yfinance recommendations: rows are periods (0m, -1m, ...), columns are grades
        # Convert to list of dicts
        recs = recommendations.where(pd.notna(recommendations), None).to_dict(orient="records")

        # Get latest grades (first row = 0m = current month)
        grades = {"buy": 0, "hold": 0, "sell": 0}
        if recs and len(recs) > 0:
            latest = recs[0]  # First row is the most recent (0m)
            grades = {
                "buy": (latest.get("strongBuy") or 0) + (latest.get("buy") or 0),
                "hold": latest.get("hold") or 0,
                "sell": (latest.get("sell") or 0) + (latest.get("strongSell") or 0),
            }

        # Price targets
        targets = None
        try:
            price_target = stock.analyst_price_target
            if price_target:
                targets = {
                    "mean": price_target.get("mean"),
                    "median": price_target.get("median"),
                    "high": price_target.get("high"),
                    "low": price_target.get("low"),
                }
        except:
            pass

        return {
            "grades": grades,
            "price_target": targets,
            "history": recs[:10] if recs else [],
        }
    except Exception as e:
        print(f"yfinance analyst fetch error: {e}", file=sys.stderr)
        return None


def fetch_yfinance_ownership(stock: yf.Ticker) -> Optional[Dict]:
    """Fetch institutional ownership from yfinance."""
    try:
        holders = stock.institutional_holders
        if holders is None or holders.empty:
            return None

        # Convert DataFrame to list of dicts - don't transpose
        df_copy = holders.reset_index()

        # Convert column names to strings if they are Timestamps
        df_copy.columns = [str(col) if hasattr(col, '__class__') and 'Timestamp' in str(col.__class__) else col for col in df_copy.columns]

        # Convert any Timestamp columns to strings
        for col in df_copy.columns:
            if hasattr(df_copy[col].dtype, 'name') and 'datetime' in str(df_copy[col].dtype).lower():
                df_copy[col] = df_copy[col].astype(str)

        holders_list = df_copy.to_dict(orient="records")

        return {
            "holders": holders_list[:20],  # Top 20 holders
            "total_institutions": len(holders_list),
        }
    except Exception as e:
        print(f"yfinance ownership fetch error: {e}", file=sys.stderr)
        return None


def fetch_twelvedata_price(ticker: str) -> Optional[Dict]:
    """Fetch price data from Twelve Data (fallback)."""
    if not TWELVEDATA_API_KEY:
        return None

    has_quota, _ = check_quota("twelvedata")
    if not has_quota:
        return None

    try:
        import requests

        symbol = ticker.split(".")[0]
        response = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": symbol,
                "interval": "1day",
                "outputsize": 5000,
                "apikey": TWELVEDATA_API_KEY,
            },
            timeout=10,
            verify=SSL_VERIFY
        )

        increment_quota("twelvedata")
        api_calls["twelvedata"] += 1

        if response.status_code != 200:
            return None

        data = response.json()
        if "values" not in data:
            return None

        # Convert to our format
        history = []
        for item in data["values"]:
            history.append({
                "Date": item["datetime"],
                "Open": float(item["open"]),
                "High": float(item["high"]),
                "Low": float(item["low"]),
                "Close": float(item["close"]),
                "Volume": int(item["volume"]),
            })

        latest = history[0] if history else None
        return {
            "current_price": latest["Close"] if latest else None,
            "history": history,
            "source": "twelvedata",
        }
    except Exception as e:
        print(f"Twelve Data fetch error: {e}", file=sys.stderr)
        return None


def fetch_finnhub_news(ticker: str) -> Optional[List[Dict]]:
    """Fetch news from Finnhub (fallback)."""
    if not FINNHUB_API_KEY:
        return None

    has_quota, _ = check_quota("finnhub")
    if not has_quota:
        return None

    try:
        import requests

        symbol = ticker.split(".")[0]
        response = requests.get(
            "https://finnhub.io/api/v1/company-news",
            params={
                "symbol": symbol,
                "from": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                "to": datetime.now().strftime("%Y-%m-%d"),
                "token": FINNHUB_API_KEY,
            },
            timeout=10,
            verify=SSL_VERIFY
        )

        increment_quota("finnhub")
        api_calls["finnhub"] += 1

        if response.status_code != 200:
            return None

        data = response.json()
        formatted_news = []
        for item in data[:20]:
            formatted_news.append({
                "title": item.get("headline"),
                "publisher": item.get("source"),
                "link": item.get("url"),
                "published": item.get("datetime"),
                "summary": item.get("summary"),
            })

        return formatted_news
    except Exception as e:
        print(f"Finnhub news fetch error: {e}", file=sys.stderr)
        return None


def fetch_all_data(
    ticker: str,
    force_refresh: bool = False
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Fetch all data types with fallback chain.

    Returns: (data_dict, warnings_list)
    """
    global api_calls
    api_calls = {"yfinance": 0, "twelvedata": 0, "finnhub": 0}

    warnings = []
    data = {}

    # Resolve ticker for yfinance
    yf_ticker = resolve_yfinance_ticker(ticker)

    # Initialize yfinance ticker
    stock = yf.Ticker(yf_ticker)
    api_calls["yfinance"] += 1

    # Fetch price data
    price, source = fetch_with_cache(
        ticker, "price",
        lambda: fetch_yfinance_price(stock),
        "yfinance", force_refresh
    )
    if price is None:
        # Try Twelve Data fallback
        price = fetch_twelvedata_price(ticker)
    data["price"] = price
    if price is None:
        warnings.append("Price data unavailable")

    # Fetch profile
    profile, _ = fetch_with_cache(
        ticker, "profile",
        lambda: fetch_yfinance_profile(stock),
        "yfinance", force_refresh
    )
    data["profile"] = profile

    # Fetch financials
    financials, _ = fetch_with_cache(
        ticker, "financials",
        lambda: fetch_yfinance_financials(stock),
        "yfinance", force_refresh
    )
    data["financials"] = financials
    if financials is None:
        warnings.append("Financial data unavailable")

    # Fetch dividends
    dividends, _ = fetch_with_cache(
        ticker, "dividends",
        lambda: fetch_yfinance_dividends(stock),
        "yfinance", force_refresh
    )
    data["dividends"] = dividends

    # Fetch news
    news, _ = fetch_with_cache(
        ticker, "news",
        lambda: fetch_yfinance_news(stock),
        "yfinance", force_refresh
    )
    # Check if news is empty or has no valid items
    if news is None or not any(item.get("title") for item in (news or [])):
        # Try Finnhub fallback
        finnhub_news = fetch_finnhub_news(ticker)
        if finnhub_news and any(item.get("title") for item in finnhub_news):
            news = finnhub_news
    data["news"] = news

    # Fetch analyst data
    analyst, _ = fetch_with_cache(
        ticker, "analyst",
        lambda: fetch_yfinance_analyst(stock),
        "yfinance", force_refresh
    )
    data["analyst"] = analyst

    # Fetch ownership
    ownership, _ = fetch_with_cache(
        ticker, "ownership",
        lambda: fetch_yfinance_ownership(stock),
        "yfinance", force_refresh
    )
    data["ownership"] = ownership

    # Print fetch summary
    cache_stats = get_cache_stats(ticker)
    print(f"DATA_FETCH: ticker={ticker} price={'OK' if price else 'MISSING'} "
          f"financials={'OK' if financials else 'MISSING'} "
          f"dividends={'OK' if dividends else 'MISSING'} "
          f"news={'OK' if news else 'MISSING'}", file=sys.stderr)
    print(f"CACHE_HITS: {cache_stats['cache_hits']} | "
          f"API_CALLS: yfinance={api_calls['yfinance']} "
          f"twelvedata={api_calls['twelvedata']} finnhub={api_calls['finnhub']}", file=sys.stderr)

    return data, warnings