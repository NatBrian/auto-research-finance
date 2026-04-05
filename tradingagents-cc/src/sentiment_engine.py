"""
TradingAgents-CC — Sentiment Engine

Quantifies market sentiment from social media proxies, using VADER and
TextBlob for NLP scoring.  Falls back to DuckDuckGo search when no
Reddit API credentials are available.
"""

import os
from datetime import datetime, timedelta
from typing import Any

from src.utils import setup_logging

logger = setup_logging()


class SentimentEngine:
    """Multi-source sentiment scoring engine."""

    def __init__(self) -> None:
        self._reddit_client_id = os.environ.get("REDDIT_CLIENT_ID")
        self._reddit_client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
        self._reddit_user_agent = os.environ.get(
            "REDDIT_USER_AGENT", "tradingagents_cc:v1.0"
        )

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

        Uses Reddit (PRAW) if credentials are available, otherwise
        DuckDuckGo news as a proxy.

        Returns
        -------
        dict with keys: daily_scores, 7d_avg, trend
        """
        texts: list[dict] = []

        # --- Try Reddit via PRAW ---
        if self._reddit_client_id and self._reddit_client_secret:
            texts = self._fetch_reddit(ticker, lookback_days)

        # --- Fallback: DuckDuckGo ---
        if not texts:
            texts = self._fetch_ddg_proxy(ticker, lookback_days)

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
            "7d_avg": round(avg_7d, 4),
            "trend": trend,
            "total_posts": total_count,
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

    def _fetch_reddit(self, ticker: str, lookback_days: int) -> list[dict]:
        """Fetch posts mentioning *ticker* from finance subreddits."""
        texts: list[dict] = []
        try:
            import praw  # type: ignore

            reddit = praw.Reddit(
                client_id=self._reddit_client_id,
                client_secret=self._reddit_client_secret,
                user_agent=self._reddit_user_agent,
            )
            subreddits = ["wallstreetbets", "investing", "stocks"]
            for sub_name in subreddits:
                try:
                    sub = reddit.subreddit(sub_name)
                    for post in sub.search(ticker, time_filter="week", limit=20):
                        texts.append({
                            "text": f"{post.title} {post.selftext[:500]}",
                            "date": datetime.utcfromtimestamp(post.created_utc).strftime(
                                "%Y-%m-%d"
                            ),
                            "source": f"r/{sub_name}",
                        })
                except Exception:
                    continue
        except Exception as exc:
            logger.warning("Reddit fetch failed: %s", exc)
        return texts

    # ------------------------------------------------------------------
    # Private: DuckDuckGo proxy
    # ------------------------------------------------------------------

    def _fetch_ddg_proxy(self, ticker: str, lookback_days: int) -> list[dict]:
        """Use DuckDuckGo news as a sentiment text proxy."""
        texts: list[dict] = []
        try:
            from duckduckgo_search import DDGS  # type: ignore

            with DDGS() as ddgs:
                results = list(ddgs.news(
                    f"{ticker} stock sentiment reddit twitter",
                    max_results=30,
                ))
            for r in results:
                body = r.get("body") or r.get("title", "")
                texts.append({
                    "text": body[:500],
                    "date": (r.get("date") or "")[:10],
                    "source": r.get("source", "ddg"),
                })
        except Exception as exc:
            logger.warning("DuckDuckGo sentiment proxy failed: %s", exc)
        return texts
