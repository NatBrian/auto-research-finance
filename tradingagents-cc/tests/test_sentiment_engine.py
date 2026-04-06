"""Tests for src/sentiment_engine.py"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.sentiment_engine import SentimentEngine


@pytest.fixture
def engine():
    return SentimentEngine()


@pytest.fixture
def engine_with_alpha_vantage(monkeypatch):
    """Engine with Alpha Vantage key configured."""
    monkeypatch.setenv("ALPHA_VANTAGE_KEY", "test_key")
    return SentimentEngine()


@pytest.fixture
def engine_with_reddit(monkeypatch):
    """Engine with Reddit credentials configured."""
    monkeypatch.setenv("REDDIT_CLIENT_ID", "test_id")
    monkeypatch.setenv("REDDIT_CLIENT_SECRET", "test_secret")
    return SentimentEngine()


class TestComputeTextSentiment:
    def test_positive_text(self, engine):
        """Clearly positive text should have combined_score > 0."""
        result = engine.compute_text_sentiment(
            "This stock is amazing! Incredible growth, record earnings, "
            "and the future looks very bright and promising!"
        )
        assert result["combined_score"] > 0
        assert result["label"] in ("POSITIVE", "NEUTRAL")

    def test_negative_text(self, engine):
        """Clearly negative text should have combined_score < 0."""
        result = engine.compute_text_sentiment(
            "Terrible losses, company is failing badly. Revenue declining, "
            "management is incompetent, avoid this stock at all costs."
        )
        assert result["combined_score"] < 0
        assert result["label"] in ("NEGATIVE", "NEUTRAL")

    def test_returns_all_keys(self, engine):
        """Should return dict with vader_compound, textblob_polarity, combined_score, label."""
        result = engine.compute_text_sentiment("Some neutral text about markets.")
        assert "vader_compound" in result
        assert "textblob_polarity" in result
        assert "combined_score" in result
        assert "label" in result


class TestGetSocialSentiment:
    @patch("src.sentiment_engine.SentimentEngine._fetch_ddg_proxy")
    def test_returns_schema(self, mock_ddg, engine):
        """get_social_sentiment should return dict with expected keys."""
        from datetime import datetime
        mock_ddg.return_value = [
            {"text": "Stock is going up, very bullish outlook!", "date": "2024-01-05", "source": "ddg"},
            {"text": "Market is strong today with good momentum", "date": "2024-01-06", "source": "ddg"},
            {"text": "Bearish reversal expected soon though", "date": "2024-01-07", "source": "ddg"},
        ]
        result = engine.get_social_sentiment("AAPL", "2024-01-10", 7)
        assert "daily_scores" in result
        assert "7d_avg" in result
        assert "7d_avg_score" in result  # New field
        assert "trend" in result
        assert "total_posts" in result
        assert "post_volume_7d" in result  # New field
        assert "score" in result  # New field
        assert "sources_used" in result
        assert isinstance(result["daily_scores"], list)
        assert result["trend"] in ("IMPROVING", "DETERIORATING", "STABLE")
        # Verify mock was called with correct args (ticker, lookback_days, ref_date)
        assert mock_ddg.call_count == 1
        call_args = mock_ddg.call_args
        assert call_args[0][0] == "AAPL"  # ticker
        assert call_args[0][1] == 7  # lookback_days
        assert isinstance(call_args[0][2], datetime)  # ref_date

    @patch("src.sentiment_engine.SentimentEngine._fetch_alpha_vantage")
    def test_alpha_vantage_source_used(self, mock_av, engine_with_alpha_vantage):
        """When Alpha Vantage key is configured, it should be used as a source."""
        mock_av.return_value = [
            {"text": "Apple reports strong Q4 earnings", "date": "2024-01-05", "source": "Reuters"},
            {"text": "iPhone sales exceed expectations", "date": "2024-01-06", "source": "Bloomberg"},
        ]
        result = engine_with_alpha_vantage.get_social_sentiment("AAPL", "2024-01-10", 7)
        assert "alpha_vantage" in result["sources_used"]
        assert result["total_posts"] >= 2

    @patch("src.sentiment_engine.SentimentEngine._fetch_reddit")
    @patch("src.sentiment_engine.SentimentEngine._fetch_alpha_vantage")
    def test_multiple_sources_combined(
        self, mock_av, mock_reddit, engine_with_reddit, monkeypatch
    ):
        """Both Reddit and Alpha Vantage sources should be combined."""
        monkeypatch.setenv("ALPHA_VANTAGE_KEY", "test_key")
        engine = SentimentEngine()

        mock_reddit.return_value = [
            {"text": "AAPL to the moon!", "date": "2024-01-05", "source": "r/wallstreetbets"},
        ]
        mock_av.return_value = [
            {"text": "Apple announces new product", "date": "2024-01-06", "source": "Reuters"},
        ]

        result = engine.get_social_sentiment("AAPL", "2024-01-10", 7)
        assert "reddit" in result["sources_used"]
        assert "alpha_vantage" in result["sources_used"]
        assert result["total_posts"] == 2

    @patch("src.sentiment_engine.SentimentEngine._fetch_reddit")
    @patch("src.sentiment_engine.SentimentEngine._fetch_ddg_proxy")
    def test_fallback_to_duckduckgo_on_reddit_failure(
        self, mock_ddg, mock_reddit, engine_with_reddit
    ):
        """Should fall back to DuckDuckGo when Reddit fails."""
        mock_reddit.return_value = []  # Reddit returns empty
        mock_ddg.return_value = [
            {"text": "Fallback news article", "date": "2024-01-05", "source": "ddg"},
        ]

        result = engine_with_reddit.get_social_sentiment("AAPL", "2024-01-10", 7)
        assert "duckduckgo" in result["sources_used"]
        assert result["total_posts"] == 1

    @patch("src.sentiment_engine.SentimentEngine._fetch_alpha_vantage")
    @patch("src.sentiment_engine.SentimentEngine._fetch_ddg_proxy")
    def test_fallback_to_duckduckgo_on_alpha_vantage_rate_limit(
        self, mock_ddg, mock_av, engine_with_alpha_vantage
    ):
        """Should fall back to DuckDuckGo when Alpha Vantage hits rate limit."""
        mock_av.side_effect = RuntimeError("Alpha Vantage rate limit: API call frequency exceeded")
        mock_ddg.return_value = [
            {"text": "Fallback news article", "date": "2024-01-05", "source": "ddg"},
        ]

        result = engine_with_alpha_vantage.get_social_sentiment("AAPL", "2024-01-10", 7)
        assert "duckduckgo" in result["sources_used"]


class TestAlphaVantageFetch:
    def test_fetch_alpha_vantage_success(self, engine_with_alpha_vantage):
        """Test successful Alpha Vantage API call."""
        from datetime import datetime
        from unittest.mock import MagicMock, patch

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "feed": [
                {
                    "title": "Apple Stock Rises",
                    "summary": "Apple reported strong earnings.",
                    "time_published": "20240105T103000",
                    "source": "Reuters",
                    "overall_sentiment_score": 0.45,
                    "ticker_sentiment": [
                        {"ticker": "AAPL", "sentiment_score": 0.5, "relevance_score": 0.95}
                    ],
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(engine_with_alpha_vantage._session, 'get', return_value=mock_response):
            ref_date = datetime(2024, 1, 10)
            result = engine_with_alpha_vantage._fetch_alpha_vantage("AAPL", 7, ref_date)

            assert len(result) == 1
            assert result[0]["text"] == "Apple Stock Rises. Apple reported strong earnings."
            assert result[0]["date"] == "2024-01-05"
            assert result[0]["sentiment_score"] == 0.5

    def test_fetch_alpha_vantage_rate_limit(self, engine_with_alpha_vantage):
        """Test Alpha Vantage rate limit handling."""
        from datetime import datetime
        from unittest.mock import MagicMock, patch

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Note": "API call frequency exceeded. Please try again later."
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(engine_with_alpha_vantage._session, 'get', return_value=mock_response):
            ref_date = datetime(2024, 1, 10)
            with pytest.raises(RuntimeError, match="rate limit"):
                engine_with_alpha_vantage._fetch_alpha_vantage("AAPL", 7, ref_date)
