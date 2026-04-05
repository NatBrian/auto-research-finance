"""Tests for exchange adapters"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils import ConfigurationError


def _paper_config(tmp_path: Path) -> dict:
    """Build a config dict pointing the paper portfolio to a temp file."""
    return {
        "exchange": {
            "default_adapter": "paper",
            "paper": {
                "initial_cash": 100_000.0,
                "slippage_bps": 5,
            },
        },
        "data": {
            "paper_portfolio_path": str(tmp_path / "paper_portfolio.json"),
        },
    }


class TestPaperAdapterInit:
    def test_initializes_portfolio(self, tmp_path):
        """PaperAdapter should create the portfolio JSON on first init."""
        from mcp_servers.exchange_server.adapters.paper_adapter import PaperAdapter

        config = _paper_config(tmp_path)
        adapter = PaperAdapter(config)
        portfolio_path = tmp_path / "paper_portfolio.json"
        assert portfolio_path.exists()
        with open(portfolio_path) as f:
            data = json.load(f)
        assert data["cash"] == 100_000.0
        assert data["positions"] == {}


class TestPaperBuySell:
    @patch("yfinance.Ticker")
    @patch("yfinance.download")
    def test_buy_reduces_cash(self, mock_dl, mock_ticker, tmp_path):
        """Submitting a BUY order should decrease cash and add a position."""
        from mcp_servers.exchange_server.adapters.paper_adapter import PaperAdapter

        mock_ticker.return_value.info = {"currentPrice": 150.0}
        config = _paper_config(tmp_path)
        adapter = PaperAdapter(config)

        order = {
            "ticker": "AAPL",
            "action": "BUY",
            "quantity": 10,
            "order_type": "MARKET",
            "stop_loss": 140.0,
        }
        result = adapter.submit_order(order)
        assert result["status"] == "FILLED"
        assert result["filled_quantity"] == 10

        # Cash should have decreased
        with open(tmp_path / "paper_portfolio.json") as f:
            data = json.load(f)
        assert data["cash"] < 100_000.0
        assert "AAPL" in data["positions"]

    @patch("yfinance.Ticker")
    @patch("yfinance.download")
    def test_sell_increases_cash(self, mock_dl, mock_ticker, tmp_path):
        """Buy then sell should increase cash and remove position."""
        from mcp_servers.exchange_server.adapters.paper_adapter import PaperAdapter

        mock_ticker.return_value.info = {"currentPrice": 150.0}
        config = _paper_config(tmp_path)
        adapter = PaperAdapter(config)

        # Buy first
        adapter.submit_order({
            "ticker": "AAPL", "action": "BUY", "quantity": 10,
            "order_type": "MARKET", "stop_loss": 140.0,
        })
        cash_after_buy = adapter._portfolio["cash"]

        # Then sell
        result = adapter.submit_order({
            "ticker": "AAPL", "action": "SELL", "quantity": 10,
            "order_type": "MARKET", "stop_loss": 160.0,
        })
        assert result["status"] == "FILLED"
        assert adapter._portfolio["cash"] > cash_after_buy

    @patch("yfinance.Ticker")
    @patch("yfinance.download")
    def test_slippage_applied(self, mock_dl, mock_ticker, tmp_path):
        """Market buy fill price should be slightly above ask (within slippage_bps)."""
        from mcp_servers.exchange_server.adapters.paper_adapter import PaperAdapter

        mock_ticker.return_value.info = {"currentPrice": 100.0}
        config = _paper_config(tmp_path)
        config["exchange"]["paper"]["slippage_bps"] = 50  # 0.5% slippage
        adapter = PaperAdapter(config)

        result = adapter.submit_order({
            "ticker": "AAPL", "action": "BUY", "quantity": 1,
            "order_type": "MARKET", "stop_loss": 90.0,
        })
        assert result["status"] == "FILLED"
        assert result["filled_price"] > 100.0, "Buy fill should be above market due to slippage"
        assert result["filled_price"] <= 100.50, "Slippage should be within 0.5%"


class TestAlpacaAdapterConfig:
    def test_raises_on_missing_env(self, monkeypatch):
        """AlpacaAdapter should raise ConfigurationError when env vars are missing."""
        monkeypatch.delenv("ALPACA_API_KEY", raising=False)
        monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)

        from mcp_servers.exchange_server.adapters.alpaca_adapter import AlpacaAdapter
        with pytest.raises(ConfigurationError):
            AlpacaAdapter({"exchange": {"alpaca": {}}})
