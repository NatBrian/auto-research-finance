"""Tests for src/market_data.py"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.market_data import MarketDataClient
from src.utils import DataUnavailableError


@pytest.fixture
def client(tmp_path):
    """Create a MarketDataClient with a temp cache directory."""
    c = MarketDataClient()
    c._cache_dir = tmp_path / "cache"
    c._cache_dir.mkdir()
    return c


def _make_ohlcv(rows: int = 30) -> pd.DataFrame:
    """Generate synthetic OHLCV data."""
    dates = pd.date_range("2024-01-01", periods=rows, freq="B")
    import numpy as np
    close = 100 + np.cumsum(np.random.randn(rows))
    return pd.DataFrame({
        "Open": close - 0.5,
        "High": close + 1,
        "Low": close - 1,
        "Close": close,
        "Volume": np.random.randint(1_000_000, 10_000_000, rows),
    }, index=dates)


class TestGetPriceHistory:
    @patch("yfinance.download")
    def test_returns_ohlcv(self, mock_dl, client):
        """get_price_history should return a DataFrame with OHLCV columns."""
        df = _make_ohlcv()
        mock_dl.return_value = df
        result = client.get_price_history("AAPL", "2024-01-10", 30, "1d")
        assert isinstance(result, pd.DataFrame)
        assert not result.empty
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            assert col in result.columns

    @patch("yfinance.download")
    def test_caches_to_parquet(self, mock_dl, client):
        """Second call should read from cache, not call yfinance again."""
        df = _make_ohlcv()
        mock_dl.return_value = df
        client.get_price_history("AAPL", "2024-01-10", 30, "1d")
        client.get_price_history("AAPL", "2024-01-10", 30, "1d")
        assert mock_dl.call_count == 1

    @patch("yfinance.download")
    def test_unavailable_raises(self, mock_dl, client):
        """Should raise DataUnavailableError when download fails."""
        mock_dl.side_effect = Exception("network error")
        with pytest.raises(DataUnavailableError):
            client.get_price_history("AAPL", "2024-01-10", 30, "1d")

    @patch("yfinance.Ticker")
    def test_valuation_metrics_returns_dict(self, mock_ticker, client):
        """get_valuation_metrics should return a dict with expected keys."""
        mock_info = {
            "trailingPE": 25.0,
            "forwardPE": 22.0,
            "priceToBook": 10.0,
            "priceToSalesTrailing12Months": 5.0,
            "enterpriseToEbitda": 18.0,
            "pegRatio": 1.5,
            "marketCap": 3_000_000_000_000,
            "currentPrice": 150.0,
            "targetMeanPrice": 180.0,
        }
        mock_ticker.return_value.info = mock_info
        result = client.get_valuation_metrics("AAPL", "2024-01-10")
        assert isinstance(result, dict)
        assert "trailingPE" in result
        assert "currentPrice" in result
