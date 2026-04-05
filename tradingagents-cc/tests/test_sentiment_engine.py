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
        mock_ddg.return_value = [
            {"text": "Stock is going up, very bullish outlook!", "date": "2024-01-05", "source": "ddg"},
            {"text": "Market is strong today with good momentum", "date": "2024-01-06", "source": "ddg"},
            {"text": "Bearish reversal expected soon though", "date": "2024-01-07", "source": "ddg"},
        ]
        result = engine.get_social_sentiment("AAPL", "2024-01-10", 7)
        assert "daily_scores" in result
        assert "7d_avg" in result
        assert "trend" in result
        assert isinstance(result["daily_scores"], list)
        assert result["trend"] in ("IMPROVING", "DETERIORATING", "STABLE")
