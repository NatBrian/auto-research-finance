"""
TradingAgents-CC — News Fetcher

Retrieves company news, macro news, SEC filings, and event calendars.
Primary: NewsAPI (if key available)  |  Fallback: DuckDuckGo search.
"""

import os
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
import requests

from src.utils import setup_logging

logger = setup_logging()


class NewsFetcher:
    """Multi-source news aggregation client."""

    def __init__(self) -> None:
        self._newsapi_key = os.environ.get("NEWSAPI_KEY")

    # ------------------------------------------------------------------
    # Company News
    # ------------------------------------------------------------------

    def search_company_news(
        self,
        ticker: str,
        date: str,
        lookback_days: int = 14,
        max_articles: int = 20,
    ) -> list[dict[str, Any]]:
        """Fetch recent news articles about *ticker*.

        Tries NewsAPI first; falls back to DuckDuckGo.
        """
        end_dt = datetime.strptime(date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=lookback_days)

        articles: list[dict] = []

        # --- Primary: NewsAPI ---
        if self._newsapi_key:
            try:
                from newsapi import NewsApiClient  # type: ignore
                api = NewsApiClient(api_key=self._newsapi_key)
                resp = api.get_everything(
                    q=f"{ticker} stock",
                    from_param=start_dt.strftime("%Y-%m-%d"),
                    to=end_dt.strftime("%Y-%m-%d"),
                    language="en",
                    sort_by="relevancy",
                    page_size=min(max_articles, 100),
                )
                for a in resp.get("articles", [])[:max_articles]:
                    articles.append({
                        "title": a.get("title", ""),
                        "source": a.get("source", {}).get("name", ""),
                        "published_at": a.get("publishedAt", ""),
                        "url": a.get("url", ""),
                        "snippet": (a.get("description") or "")[:500],
                    })
                if articles:
                    return articles
            except Exception as exc:
                logger.warning("NewsAPI failed, falling back to DuckDuckGo: %s", exc)

        # --- Fallback: DuckDuckGo ---
        try:
            from duckduckgo_search import DDGS  # type: ignore
            with DDGS() as ddgs:
                results = list(ddgs.news(
                    f"{ticker} stock",
                    max_results=max_articles,
                ))
            for r in results:
                pub = r.get("date", "")
                articles.append({
                    "title": r.get("title", ""),
                    "source": r.get("source", ""),
                    "published_at": pub,
                    "url": r.get("url", ""),
                    "snippet": (r.get("body") or "")[:500],
                })
        except Exception as exc:
            logger.warning("DuckDuckGo news search failed: %s", exc)

        return articles[:max_articles]

    # ------------------------------------------------------------------
    # Macro News
    # ------------------------------------------------------------------

    def search_macro_news(
        self,
        date: str,
        lookback_days: int = 7,
        topics: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for macro-economic news across multiple topics."""
        if topics is None:
            topics = [
                "federal reserve", "interest rates", "inflation",
                "gdp", "recession", "tariffs", "geopolitics",
            ]

        all_articles: list[dict] = []
        seen_urls: set[str] = set()

        try:
            from duckduckgo_search import DDGS  # type: ignore
            with DDGS() as ddgs:
                for topic in topics:
                    try:
                        results = list(ddgs.news(
                            f"{topic} economy markets",
                            max_results=5,
                        ))
                        for r in results:
                            url = r.get("url", "")
                            if url in seen_urls:
                                continue
                            seen_urls.add(url)
                            all_articles.append({
                                "title": r.get("title", ""),
                                "source": r.get("source", ""),
                                "published_at": r.get("date", ""),
                                "url": url,
                                "snippet": (r.get("body") or "")[:500],
                                "topic": topic,
                            })
                    except Exception:
                        continue
        except Exception as exc:
            logger.warning("Macro news search failed: %s", exc)

        # Sort by recency (best-effort string sort on date field)
        all_articles.sort(key=lambda a: a.get("published_at", ""), reverse=True)
        return all_articles[:10]

    # ------------------------------------------------------------------
    # SEC Filings
    # ------------------------------------------------------------------

    def get_recent_sec_filings(
        self, ticker: str, lookback_days: int = 30
    ) -> list[dict[str, Any]]:
        """Fetch recent SEC filings via yfinance or SEC EDGAR public API."""
        filings: list[dict] = []

        # --- Try yfinance ---
        try:
            import yfinance as yf  # type: ignore
            t = yf.Ticker(ticker)
            sec = getattr(t, "sec_filings", None)
            if sec is not None and hasattr(sec, "__iter__"):
                for f in sec:
                    if isinstance(f, dict):
                        filings.append({
                            "filing_type": f.get("type", ""),
                            "date": str(f.get("date", "")),
                            "description": f.get("title", ""),
                            "url": f.get("edgarUrl", ""),
                        })
                if filings:
                    return filings[:20]
        except Exception:
            pass

        # --- Fallback: SEC EDGAR public API ---
        try:
            # Resolve CIK from ticker
            cik_url = (
                f"https://efts.sec.gov/LATEST/search-index?"
                f"q=%22{ticker}%22&dateRange=custom"
            )
            # Use the company tickers JSON from SEC
            tickers_url = "https://www.sec.gov/files/company_tickers.json"
            headers = {"User-Agent": "TradingAgentsCC/1.0 research@example.com"}
            resp = requests.get(tickers_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                cik = None
                for entry in data.values():
                    if entry.get("ticker", "").upper() == ticker.upper():
                        cik = str(entry["cik_str"]).zfill(10)
                        break
                if cik:
                    sub_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
                    resp2 = requests.get(sub_url, headers=headers, timeout=10)
                    if resp2.status_code == 200:
                        sub_data = resp2.json()
                        recent = sub_data.get("filings", {}).get("recent", {})
                        forms = recent.get("form", [])
                        dates = recent.get("filingDate", [])
                        descs = recent.get("primaryDocDescription", [])
                        accessions = recent.get("accessionNumber", [])
                        cutoff = (
                            datetime.now() - timedelta(days=lookback_days)
                        ).strftime("%Y-%m-%d")
                        for i in range(min(len(forms), 20)):
                            if dates[i] >= cutoff:
                                filings.append({
                                    "filing_type": forms[i],
                                    "date": dates[i],
                                    "description": descs[i] if i < len(descs) else "",
                                    "url": (
                                        f"https://www.sec.gov/Archives/edgar/data/"
                                        f"{cik}/{accessions[i].replace('-', '')}/"
                                    ) if i < len(accessions) else "",
                                })
        except Exception as exc:
            logger.warning("SEC EDGAR lookup failed for %s: %s", ticker, exc)

        return filings

    # ------------------------------------------------------------------
    # Event Calendar
    # ------------------------------------------------------------------

    def get_event_calendar(
        self, ticker: str, lookahead_days: int = 30
    ) -> list[dict[str, Any]]:
        """Return upcoming events (earnings, dividends, etc.)."""
        events: list[dict] = []
        try:
            import yfinance as yf  # type: ignore
            t = yf.Ticker(ticker)
            cal = t.calendar
            if cal is not None:
                if isinstance(cal, dict):
                    for key, val in cal.items():
                        events.append({
                            "event": str(key),
                            "date": str(val),
                            "expected_impact": "MEDIUM",
                        })
                elif isinstance(cal, pd.DataFrame):
                    for col in cal.columns:
                        events.append({
                            "event": str(col),
                            "date": str(cal[col].iloc[0]) if len(cal[col]) > 0 else "",
                            "expected_impact": "MEDIUM",
                        })
        except Exception as exc:
            logger.warning("Event calendar unavailable for %s: %s", ticker, exc)

        return events
