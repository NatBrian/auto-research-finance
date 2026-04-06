"""
TradingAgents-CC — Sentiment Engine

Quantifies market sentiment from multiple sources:
  - Reddit (PRAW) for social media sentiment
  - Alpha Vantage NEWS_SENTIMENT API for news-based sentiment
  - DuckDuckGo news as additional source (always combined)

Uses VADER and TextBlob for NLP scoring.
"""

import os
from datetime import datetime, timedelta
from typing import Any

import requests
import urllib3

from src.utils import setup_logging, load_config

logger = setup_logging()


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


class SentimentEngine:
    """Multi-source sentiment scoring engine.

    Sources are combined: Reddit + Alpha Vantage + DuckDuckGo (always).
    Falls back gracefully when individual sources fail.
    """

    def __init__(self) -> None:
        self._reddit_client_id = os.environ.get("REDDIT_CLIENT_ID")
        self._reddit_client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
        self._reddit_user_agent = os.environ.get(
            "REDDIT_USER_AGENT", "tradingagents_cc:v1.0"
        )
        self._alpha_vantage_key = os.environ.get("ALPHA_VANTAGE_KEY")

        # Create session with SSL verification setting from config
        self._session = requests.Session()
        self._session.verify = _ssl_verify

    # ------------------------------------------------------------------
    # Social Sentiment
    # ------------------------------------------------------------------

    def get_social_sentiment(
        self,
        ticker: str,
        date: str,
        lookback_days: int = 7,
    ) -> dict[str, Any]:
        """Aggregate social media sentiment for *ticker*.

        Combines all available sources: Reddit + Alpha Vantage + DuckDuckGo.
        Each source is fetched independently; failures don't block others.

        Parameters
        ----------
        ticker : str
            Stock ticker symbol to analyze.
        date : str
            Reference date (YYYY-MM-DD) for calculating lookback window.
        lookback_days : int
            Number of days to look back for sentiment data.

        Returns
        -------
        dict with keys: daily_scores, 7d_avg, trend, total_posts, sources_used
        """
        texts: list[dict] = []
        sources_tried: list[str] = []
        sources_used: list[str] = []

        # Parse reference date for lookback calculation
        try:
            ref_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            ref_date = datetime.utcnow()

        # --- Try Reddit via PRAW ---
        if self._reddit_client_id and self._reddit_client_secret:
            sources_tried.append("reddit")
            logger.info("Fetching sentiment from Reddit for %s", ticker)
            try:
                reddit_texts = self._fetch_reddit(ticker, lookback_days, ref_date)
                if reddit_texts:
                    texts.extend(reddit_texts)
                    sources_used.append("reddit")
                    logger.info("Reddit returned %d posts", len(reddit_texts))
            except Exception as exc:
                logger.warning("Reddit fetch failed: %s", exc)

        # --- Try Alpha Vantage NEWS_SENTIMENT ---
        if self._alpha_vantage_key:
            sources_tried.append("alpha_vantage")
            logger.info("Fetching sentiment from Alpha Vantage for %s", ticker)
            try:
                av_texts = self._fetch_alpha_vantage(ticker, lookback_days, ref_date)
                if av_texts:
                    texts.extend(av_texts)
                    sources_used.append("alpha_vantage")
                    logger.info("Alpha Vantage returned %d articles", len(av_texts))
            except Exception as exc:
                logger.warning("Alpha Vantage fetch failed: %s", exc)

        # --- Always include DuckDuckGo (combined with other sources) ---
        sources_tried.append("duckduckgo")
        logger.info("Fetching sentiment from DuckDuckGo for %s", ticker)
        try:
            ddg_texts = self._fetch_ddg_proxy(ticker, lookback_days, ref_date)
            if ddg_texts:
                texts.extend(ddg_texts)
                sources_used.append("duckduckgo")
                logger.info("DuckDuckGo returned %d articles", len(ddg_texts))
        except Exception as exc:
            logger.warning("DuckDuckGo fetch failed: %s", exc)

        # Log if no data found from any source
        if not texts:
            logger.warning(
                "No sentiment data found for %s from any source (tried: %s)",
                ticker,
                ", ".join(sources_tried),
            )

        # --- Score each text ---
        daily_map: dict[str, list[float]] = {}
        total_count = 0
        for item in texts:
            score_data = self.compute_text_sentiment(item.get("text", ""))
            day_key = item.get("date", date)[:10]
            daily_map.setdefault(day_key, []).append(score_data["combined_score"])
            total_count += 1

        # --- Build daily scores ---
        daily_scores: list[dict] = []
        for day_key in sorted(daily_map.keys()):
            scores = daily_map[day_key]
            avg_compound = sum(scores) / len(scores) if scores else 0.0
            daily_scores.append({
                "date": day_key,
                "positive": max(0, avg_compound),
                "negative": min(0, avg_compound),
                "compound": round(avg_compound, 4),
                "post_count": len(scores),
            })

        # --- 7-day weighted average (recent days weighted higher) ---
        if daily_scores:
            weights = list(range(1, len(daily_scores) + 1))
            total_w = sum(weights)
            avg_7d = sum(
                s["compound"] * w for s, w in zip(daily_scores, weights)
            ) / total_w
        else:
            avg_7d = 0.0

        # --- Trend detection ---
        if len(daily_scores) >= 3:
            first_half = [s["compound"] for s in daily_scores[: len(daily_scores) // 2]]
            second_half = [s["compound"] for s in daily_scores[len(daily_scores) // 2 :]]
            avg_first = sum(first_half) / len(first_half)
            avg_second = sum(second_half) / len(second_half)
            if avg_second > avg_first + 0.05:
                trend = "IMPROVING"
            elif avg_second < avg_first - 0.05:
                trend = "DETERIORATING"
            else:
                trend = "STABLE"
        else:
            trend = "STABLE"

        return {
            "daily_scores": daily_scores,
            "7d_avg_score": round(avg_7d, 4),
            "7d_avg": round(avg_7d, 4),  # Keep both for backward compatibility
            "trend": trend,
            "post_volume_7d": total_count,
            "total_posts": total_count,  # Keep both for backward compatibility
            "score": round(avg_7d, 4),  # Alias for skill compatibility
            "sources_used": sources_used,
        }

    # ------------------------------------------------------------------
    # Text Sentiment (VADER + TextBlob)
    # ------------------------------------------------------------------

    def compute_text_sentiment(self, text: str) -> dict[str, Any]:
        """Score a text snippet using VADER (primary) and TextBlob (secondary).

        Returns
        -------
        dict with vader_compound, textblob_polarity, combined_score, label
        """
        # VADER
        vader_compound = 0.0
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore
            analyzer = SentimentIntensityAnalyzer()
            vs = analyzer.polarity_scores(text)
            vader_compound = vs.get("compound", 0.0)
        except Exception as exc:
            logger.warning("VADER scoring failed: %s", exc)

        # TextBlob
        textblob_polarity = 0.0
        try:
            from textblob import TextBlob  # type: ignore
            blob = TextBlob(text)
            textblob_polarity = blob.sentiment.polarity
        except Exception as exc:
            logger.warning("TextBlob scoring failed: %s", exc)

        # Combined (70% VADER, 30% TextBlob)
        combined = vader_compound * 0.7 + textblob_polarity * 0.3

        # Label
        if combined >= 0.3:
            label = "POSITIVE"
        elif combined <= -0.3:
            label = "NEGATIVE"
        else:
            label = "NEUTRAL"

        return {
            "vader_compound": round(vader_compound, 4),
            "textblob_polarity": round(textblob_polarity, 4),
            "combined_score": round(combined, 4),
            "label": label,
        }

    # ------------------------------------------------------------------
    # Private: Reddit
    # ------------------------------------------------------------------

    def _fetch_reddit(self, ticker: str, lookback_days: int, ref_date: datetime) -> list[dict]:
        """Fetch posts mentioning *ticker* from finance subreddits.

        Parameters
        ----------
        ticker : str
            Stock ticker symbol to search for.
        lookback_days : int
            Number of days to look back (mapped to Reddit time_filter).
        ref_date : datetime
            Reference date for calculating the lookback window.

        Returns
        -------
        list of dicts with keys: text, date, source
        """
        texts: list[dict] = []
        try:
            import praw  # type: ignore

            # Configure Reddit instance
            reddit = praw.Reddit(
                client_id=self._reddit_client_id,
                client_secret=self._reddit_client_secret,
                user_agent=self._reddit_user_agent,
            )

            # Disable SSL verification for prawcore if configured
            if not _ssl_verify:
                # Monkey-patch the session used by prawcore
                import prawcore.sessions
                prawcore.sessions._session = self._session

            # Map lookback_days to Reddit's time_filter options
            if lookback_days <= 1:
                time_filter = "day"
            elif lookback_days <= 7:
                time_filter = "week"
            elif lookback_days <= 30:
                time_filter = "month"
            else:
                time_filter = "year"

            subreddits = ["wallstreetbets", "investing", "stocks"]
            cutoff_date = ref_date - timedelta(days=lookback_days)

            for sub_name in subreddits:
                try:
                    sub = reddit.subreddit(sub_name)
                    for post in sub.search(ticker, time_filter=time_filter, limit=20):
                        post_date = datetime.utcfromtimestamp(post.created_utc)
                        # Double-check the post is within lookback window
                        if post_date < cutoff_date:
                            continue
                        texts.append({
                            "text": f"{post.title} {post.selftext[:500]}",
                            "date": post_date.strftime("%Y-%m-%d"),
                            "source": f"r/{sub_name}",
                        })
                except Exception:
                    continue
        except Exception as exc:
            logger.warning("Reddit fetch failed: %s", exc)
        return texts

    # ------------------------------------------------------------------
    # Private: Alpha Vantage
    # ------------------------------------------------------------------

    def _fetch_alpha_vantage(
        self, ticker: str, lookback_days: int, ref_date: datetime
    ) -> list[dict]:
        """Fetch news sentiment from Alpha Vantage NEWS_SENTIMENT API.

        Parameters
        ----------
        ticker : str
            Stock ticker symbol to search for.
        lookback_days : int
            Number of days to look back for news articles.
        ref_date : datetime
            Reference date for calculating the lookback window.

        Returns
        -------
        list of dicts with keys: text, date, source, sentiment_score

        Raises
        ------
        RuntimeError
            If API returns rate limit error or other critical failures.
        """
        texts: list[dict] = []

        # Calculate time range in Alpha Vantage format (YYYYMMDDTHHMM)
        time_to = ref_date.strftime("%Y%m%dT0000")
        time_from = (ref_date - timedelta(days=lookback_days)).strftime("%Y%m%dT0000")

        url = "https://www.alphavantage.co/query"
        params = {
            "function": "NEWS_SENTIMENT",
            "tickers": ticker,
            "time_from": time_from,
            "time_to": time_to,
            "sort": "LATEST",
            "limit": 50,
            "apikey": self._alpha_vantage_key,
        }

        response = self._session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Check for API errors (rate limit, invalid key, etc.)
        if "Error Message" in data:
            raise RuntimeError(f"Alpha Vantage API error: {data['Error Message']}")
        if "Note" in data:
            # Rate limit message from Alpha Vantage
            raise RuntimeError(f"Alpha Vantage rate limit: {data['Note']}")
        if "Information" in data:
            # API call frequency limit
            raise RuntimeError(f"Alpha Vantage limit: {data['Information']}")

        # Parse news items
        items = data.get("feed", [])
        cutoff_date = ref_date - timedelta(days=lookback_days)

        for item in items:
            # Extract relevant ticker sentiment
            ticker_sentiment = None
            for ts in item.get("ticker_sentiment", []):
                if ts.get("ticker") == ticker:
                    ticker_sentiment = ts
                    break

            # Use ticker-specific sentiment if available, otherwise overall
            if ticker_sentiment:
                sentiment_score = float(ticker_sentiment.get("sentiment_score", 0))
                relevance = float(ticker_sentiment.get("relevance_score", 0))
            else:
                sentiment_score = float(item.get("overall_sentiment_score", 0))
                relevance = 1.0

            # Skip low-relevance articles
            if relevance < 0.3:
                continue

            # Parse publication date
            time_published = item.get("time_published", "")
            try:
                pub_date = datetime.strptime(time_published[:8], "%Y%m%d")
                if pub_date < cutoff_date:
                    continue
                date_str = pub_date.strftime("%Y-%m-%d")
            except ValueError:
                date_str = ref_date.strftime("%Y-%m-%d")

            # Build text from title and summary
            title = item.get("title", "")
            summary = item.get("summary", "")
            text = f"{title}. {summary}"[:500]

            texts.append({
                "text": text,
                "date": date_str,
                "source": item.get("source", "alpha_vantage"),
                "sentiment_score": sentiment_score,
                "relevance": relevance,
            })

        return texts

    # ------------------------------------------------------------------
    # Private: DuckDuckGo proxy
    # ------------------------------------------------------------------

    def _fetch_ddg_proxy(self, ticker: str, lookback_days: int, ref_date: datetime) -> list[dict]:
        """Use DuckDuckGo news as a sentiment text proxy.

        Parameters
        ----------
        ticker : str
            Stock ticker symbol to search for.
        lookback_days : int
            Number of days to look back for news articles.
        ref_date : datetime
            Reference date for calculating the lookback window.

        Returns
        -------
        list of dicts with keys: text, date, source
        """
        texts: list[dict] = []
        try:
            from duckduckgo_search import DDGS  # type: ignore

            cutoff_date = ref_date - timedelta(days=lookback_days)

            with DDGS() as ddgs:
                results = list(ddgs.news(
                    f"{ticker} stock sentiment reddit twitter",
                    max_results=30,
                ))
            for r in results:
                body = r.get("body") or r.get("title", "")
                raw_date = r.get("date", "")
                # Parse and validate date, default to ref_date if missing/invalid
                if raw_date and len(raw_date) >= 10:
                    parsed_date = raw_date[:10]
                else:
                    parsed_date = ref_date.strftime("%Y-%m-%d")

                # Filter out articles older than lookback window
                try:
                    article_date = datetime.strptime(parsed_date, "%Y-%m-%d")
                    if article_date < cutoff_date:
                        continue
                except ValueError:
                    # Keep article if date parsing fails
                    pass

                texts.append({
                    "text": body[:500],
                    "date": parsed_date,
                    "source": r.get("source", "ddg"),
                })
        except Exception as exc:
            logger.warning("DuckDuckGo sentiment proxy failed: %s", exc)
        return texts
