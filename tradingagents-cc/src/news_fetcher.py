"""
TradingAgents-CC — News Fetcher

Retrieves company news, macro news, SEC filings, and event calendars.
Primary sources: Yahoo Finance (yfinance), NewsAPI
Fallback: DuckDuckGo search
"""

import os
import time
import urllib3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.utils import get_project_root, load_config, setup_logging

logger = setup_logging()

# Cache duration in seconds (30 minutes for news)
NEWS_CACHE_TTL_SECONDS = 1800


def _get_ssl_verify() -> bool:
    """Read SSL verify setting from config. Defaults to True for security."""
    try:
        config = load_config()
        return config.get("ssl", {}).get("verify", True)
    except Exception:
        return True


# Disable SSL warnings only if verify=False in config
_ssl_verify = _get_ssl_verify()
if not _ssl_verify:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class NewsFetcher:
    """Multi-source news aggregation client with caching support.

    News sources are merged for comprehensive coverage:
    - Primary: Yahoo Finance + NewsAPI (both fetched, deduplicated)
    - Fallback: If one source fails, supplement with DuckDuckGo
    - Final fallback: DuckDuckGo only

    Example source combinations:
    - yahoo+newsapi (ideal)
    - yahoo+duckduckgo (if NewsAPI fails)
    - newsapi+duckduckgo (if Yahoo fails)
    - duckduckgo (if both fail)
    """

    def __init__(self) -> None:
        self._newsapi_key = os.environ.get("NEWSAPI_KEY")
        self._session = requests.Session()
        self._session.verify = _ssl_verify
        self._cache_dir = get_project_root() / "data" / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        # Create yfinance session with SSL config from settings
        # Set ssl.verify: false in config/settings.yaml for corporate proxy environments
        self._yf_session = None
        if not _ssl_verify:
            try:
                from curl_cffi.requests import Session as CurlSession
                self._yf_session = CurlSession(verify=False)
            except ImportError:
                logger.warning("curl_cffi not available, yfinance may fail with SSL errors in proxy environments")

    def _get_cache_path(self, cache_key: str) -> Path:
        """Generate cache file path for a given key."""
        return self._cache_dir / f"news_{cache_key}.json"

    def _read_cache(self, cache_key: str) -> list[dict] | None:
        """Read from cache if exists and not expired."""
        import json
        cache_path = self._get_cache_path(cache_key)
        if not cache_path.exists():
            return None
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cached_at = data.get("cached_at", 0)
            if time.time() - cached_at > NEWS_CACHE_TTL_SECONDS:
                return None
            return data.get("articles", [])
        except Exception:
            return None

    def _write_cache(self, cache_key: str, articles: list[dict]) -> None:
        """Write articles to cache."""
        import json
        cache_path = self._get_cache_path(cache_key)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({
                    "cached_at": time.time(),
                    "articles": articles,
                }, f)
        except Exception as exc:
            logger.warning("Failed to cache news data: %s", exc)

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
        """Fetch recent news articles about *ticker* from multiple sources.

        Sources are merged for comprehensive coverage:
        - Primary: Yahoo Finance + NewsAPI (both fetched, deduplicated)
        - Fallback: If one fails, supplement with DuckDuckGo
        - Final fallback: DuckDuckGo only

        Results are cached for 30 minutes.
        """
        # Check cache first
        cache_key = f"{ticker}_{date}_{lookback_days}_{max_articles}"
        cached = self._read_cache(cache_key)
        if cached is not None:
            logger.info("Cache hit for company news: %s", ticker)
            return cached

        all_articles: list[dict] = []
        seen_urls: set[str] = set()
        sources_used: list[str] = []

        # --- Fetch from Yahoo Finance ---
        yf_articles = self._fetch_news_yahoo(ticker, max_articles)
        if yf_articles:
            sources_used.append("yahoo")
            for a in yf_articles:
                url = a.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_articles.append(a)
            logger.info("Yahoo Finance: %d articles for %s", len(yf_articles), ticker)

        # --- Fetch from NewsAPI ---
        newsapi_articles = []
        if self._newsapi_key:
            newsapi_articles = self._fetch_news_newsapi(ticker, date, lookback_days, max_articles)
            if newsapi_articles:
                sources_used.append("newsapi")
                for a in newsapi_articles:
                    url = a.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_articles.append(a)
                logger.info("NewsAPI: %d articles for %s", len(newsapi_articles), ticker)

        # --- Fallback to DuckDuckGo if needed ---
        # Use DDG if: both primary sources failed, or only one succeeded (supplement)
        need_ddg = len(sources_used) < 2 or len(all_articles) < max_articles // 2
        if need_ddg:
            ddg_articles = self._fetch_news_duckduckgo(ticker, max_articles)
            if ddg_articles:
                sources_used.append("duckduckgo")
                ddg_count = 0
                for a in ddg_articles:
                    url = a.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_articles.append(a)
                        ddg_count += 1
                logger.info("DuckDuckGo: %d articles for %s", ddg_count, ticker)

        # Sort by publication date (newest first)
        all_articles.sort(key=lambda a: a.get("published_at", ""), reverse=True)

        # Limit to max_articles
        result = all_articles[:max_articles]

        # Cache the results
        if result:
            self._write_cache(cache_key, result)
            logger.info(
                "Total: %d articles for %s from sources: %s",
                len(result), ticker, "+".join(sources_used)
            )
        else:
            logger.warning("No news articles found for %s from any source", ticker)

        return result

    def _fetch_news_yahoo(self, ticker: str, max_articles: int) -> list[dict]:
        """Fetch news from Yahoo Finance via yfinance."""
        articles: list[dict] = []
        try:
            import yfinance as yf  # type: ignore

            # Use session with SSL verification disabled for proxy environments
            if self._yf_session:
                t = yf.Ticker(ticker, session=self._yf_session)
            else:
                t = yf.Ticker(ticker)

            news = t.news
            if news is None or not hasattr(news, "__iter__"):
                return articles

            for item in news[:max_articles]:
                try:
                    # yfinance news structure: nested 'content' dict
                    if isinstance(item, dict):
                        content = item.get("content", item)

                        # Extract title
                        title = content.get("title", item.get("title", ""))

                        # Extract publisher (nested in provider.displayName)
                        provider = content.get("provider", {})
                        publisher = provider.get("displayName", provider.get("name", "")) if provider else ""

                        # Extract publication date
                        pub_date = content.get("pubDate", item.get("providerPublishTime", ""))

                        # Convert timestamp if numeric
                        if isinstance(pub_date, (int, float)):
                            pub_date = datetime.fromtimestamp(pub_date).strftime("%Y-%m-%d %H:%M:%S")

                        # Extract URL
                        canonical_url = content.get("canonicalUrl", {})
                        link = canonical_url.get("url", item.get("link", ""))

                        # Extract summary
                        summary = content.get("summary", content.get("description", ""))

                        articles.append({
                            "title": title,
                            "source": f"Yahoo Finance - {publisher}" if publisher else "Yahoo Finance",
                            "published_at": str(pub_date),
                            "url": link,
                            "snippet": (summary or "")[:500],
                        })
                except Exception:
                    continue
        except Exception as exc:
            logger.warning("Yahoo Finance news fetch failed for %s: %s", ticker, exc)

        return articles

    def _fetch_news_newsapi(
        self, ticker: str, date: str, lookback_days: int, max_articles: int
    ) -> list[dict]:
        """Fetch news from NewsAPI."""
        articles: list[dict] = []
        try:
            end_dt = datetime.strptime(date, "%Y-%m-%d")
            start_dt = end_dt - timedelta(days=lookback_days)

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
                    "source": f"NewsAPI - {a.get('source', {}).get('name', '')}",
                    "published_at": a.get("publishedAt", ""),
                    "url": a.get("url", ""),
                    "snippet": (a.get("description") or "")[:500],
                })
        except Exception as exc:
            logger.warning("NewsAPI fetch failed for %s: %s", ticker, exc)

        return articles

    def _fetch_news_duckduckgo(self, ticker: str, max_articles: int) -> list[dict]:
        """Fetch news from DuckDuckGo as fallback."""
        articles: list[dict] = []
        try:
            from duckduckgo_search import DDGS  # type: ignore
            with DDGS() as ddgs:
                results = list(ddgs.news(
                    f"{ticker} stock",
                    max_results=max_articles,
                ))
            for r in results:
                articles.append({
                    "title": r.get("title", ""),
                    "source": f"DuckDuckGo - {r.get('source', '')}",
                    "published_at": r.get("date", ""),
                    "url": r.get("url", ""),
                    "snippet": (r.get("body") or "")[:500],
                })
        except Exception as exc:
            logger.warning("DuckDuckGo news search failed for %s: %s", ticker, exc)

        return articles

    # ------------------------------------------------------------------
    # Macro News
    # ------------------------------------------------------------------

    def search_macro_news(
        self,
        date: str,
        lookback_days: int = 7,
        topics: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for macro-economic news across multiple topics.

        Sources are merged for comprehensive coverage:
        - Primary: NewsAPI (if available)
        - Fallback/supplement: DuckDuckGo

        Results are cached for 30 minutes.
        """
        if topics is None:
            topics = [
                "federal reserve", "interest rates", "inflation",
                "gdp", "recession", "tariffs", "geopolitics",
            ]

        # Check cache first
        topics_key = ",".join(sorted(topics))
        cache_key = f"macro_{date}_{lookback_days}_{topics_key}"
        cached = self._read_cache(cache_key)
        if cached is not None:
            logger.info("Cache hit for macro news")
            return cached

        all_articles: list[dict] = []
        seen_urls: set[str] = set()
        sources_used: list[str] = []

        # --- Fetch from NewsAPI ---
        if self._newsapi_key:
            newsapi_articles = self._fetch_macro_newsapi(date, lookback_days, topics)
            if newsapi_articles:
                sources_used.append("newsapi")
                for a in newsapi_articles:
                    url = a.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_articles.append(a)
                logger.info("NewsAPI: %d macro articles", len(newsapi_articles))

        # --- Fetch from DuckDuckGo (supplement or fallback) ---
        ddg_articles = self._fetch_macro_duckduckgo(date, lookback_days, topics)
        if ddg_articles:
            sources_used.append("duckduckgo")
            ddg_count = 0
            for a in ddg_articles:
                url = a.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_articles.append(a)
                    ddg_count += 1
            logger.info("DuckDuckGo: %d macro articles", ddg_count)

        # Sort by publication date (newest first)
        all_articles.sort(key=lambda a: a.get("published_at", ""), reverse=True)

        # Limit to 10 articles
        result = all_articles[:10]

        # Cache the results
        if result:
            self._write_cache(cache_key, result)
            logger.info(
                "Total: %d macro articles from sources: %s",
                len(result), "+".join(sources_used)
            )
        else:
            logger.warning("No macro news articles found from any source")

        return result

    def _fetch_macro_newsapi(
        self, date: str, lookback_days: int, topics: list[str]
    ) -> list[dict]:
        """Fetch macro news from NewsAPI."""
        articles: list[dict] = []
        seen_urls: set[str] = set()

        try:
            end_dt = datetime.strptime(date, "%Y-%m-%d")
            start_dt = end_dt - timedelta(days=lookback_days)

            from newsapi import NewsApiClient  # type: ignore
            api = NewsApiClient(api_key=self._newsapi_key)

            # Build query for macro topics
            query = " OR ".join(topics[:4])  # NewsAPI has query length limits

            resp = api.get_everything(
                q=query,
                from_param=start_dt.strftime("%Y-%m-%d"),
                to=end_dt.strftime("%Y-%m-%d"),
                language="en",
                sort_by="publishedAt",
                page_size=20,
            )

            for a in resp.get("articles", []):
                url = a.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Determine which topic this article relates to
                title_lower = (a.get("title", "") + " " + (a.get("description") or "")).lower()
                matched_topic = "general"
                for topic in topics:
                    if topic.lower() in title_lower:
                        matched_topic = topic
                        break

                articles.append({
                    "title": a.get("title", ""),
                    "source": f"NewsAPI - {a.get('source', {}).get('name', '')}",
                    "published_at": a.get("publishedAt", ""),
                    "url": url,
                    "snippet": (a.get("description") or "")[:500],
                    "topic": matched_topic,
                })
        except Exception as exc:
            logger.warning("NewsAPI macro news fetch failed: %s", exc)

        # Sort by recency
        articles.sort(key=lambda a: a.get("published_at", ""), reverse=True)
        return articles[:10]

    def _fetch_macro_duckduckgo(
        self, date: str, lookback_days: int, topics: list[str]
    ) -> list[dict]:
        """Fetch macro news from DuckDuckGo as fallback."""
        articles: list[dict] = []
        seen_urls: set[str] = set()

        # Calculate date filter cutoff
        try:
            cutoff_date = datetime.strptime(date, "%Y-%m-%d") - timedelta(days=lookback_days)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d")
        except ValueError:
            cutoff_str = None

        try:
            from duckduckgo_search import DDGS  # type: ignore
            with DDGS() as ddgs:
                for i, topic in enumerate(topics):
                    # Add small delay between topic searches to avoid rate limiting
                    if i > 0:
                        time.sleep(0.5)
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

                            # Filter by date if cutoff is set
                            pub_date = r.get("date", "")[:10] if r.get("date") else ""
                            if cutoff_str and pub_date and pub_date < cutoff_str:
                                continue

                            articles.append({
                                "title": r.get("title", ""),
                                "source": f"DuckDuckGo - {r.get('source', '')}",
                                "published_at": r.get("date", ""),
                                "url": url,
                                "snippet": (r.get("body") or "")[:500],
                                "topic": topic,
                            })
                    except Exception:
                        continue
        except Exception as exc:
            logger.warning("DuckDuckGo macro news search failed: %s", exc)

        # Sort by recency (best-effort string sort on date field)
        articles.sort(key=lambda a: a.get("published_at", ""), reverse=True)
        return articles[:10]

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
            # Use the company tickers JSON from SEC to resolve CIK
            tickers_url = "https://www.sec.gov/files/company_tickers.json"
            headers = {"User-Agent": "TradingAgentsCC/1.0 research@example.com"}
            resp = self._session.get(tickers_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                cik = None
                for entry in data.values():
                    if entry.get("ticker", "").upper() == ticker.upper():
                        cik = str(entry["cik_str"]).zfill(10)
                        break
                if cik:
                    sub_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
                    resp2 = self._session.get(sub_url, headers=headers, timeout=10)
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
        """Return upcoming events (earnings, dividends, etc.) within lookahead window."""
        events: list[dict] = []
        try:
            import yfinance as yf  # type: ignore

            # Use session with SSL verification disabled for proxy environments
            if self._yf_session:
                t = yf.Ticker(ticker, session=self._yf_session)
            else:
                t = yf.Ticker(ticker)

            cal = t.calendar
            cutoff_date = datetime.now() + timedelta(days=lookahead_days)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d")

            if cal is not None:
                if isinstance(cal, dict):
                    for key, val in cal.items():
                        date_str = str(val)[:10] if val else ""
                        # Filter events within lookahead window
                        if date_str and date_str <= cutoff_str:
                            events.append({
                                "event": str(key),
                                "date": date_str,
                                "expected_impact": "MEDIUM",
                            })
                elif isinstance(cal, pd.DataFrame):
                    for col in cal.columns:
                        try:
                            date_val = cal[col].iloc[0] if len(cal[col]) > 0 else None
                            date_str = str(date_val)[:10] if date_val else ""
                            # Filter events within lookahead window
                            if date_str and date_str <= cutoff_str:
                                events.append({
                                    "event": str(col),
                                    "date": date_str,
                                    "expected_impact": "MEDIUM",
                                })
                        except Exception:
                            continue
        except Exception as exc:
            logger.warning("Event calendar unavailable for %s: %s", ticker, exc)

        return events