"""Tests for src/order_validator.py"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.order_validator import validate_order


def _valid_buy_order() -> dict:
    """Return a complete, valid BUY order."""
    return {
        "ticker": "AAPL",
        "action": "BUY",
        "quantity": 10,
        "order_type": "MARKET",
        "limit_price": None,
        "stop_loss": 140.0,
        "take_profit": 180.0,
        "current_price": 150.0,
    }


class TestValidOrders:
    def test_valid_buy_order_passes(self):
        """A complete valid BUY order should pass validation."""
        result = validate_order(_valid_buy_order())
        assert result["valid"] is True
        assert len(result["errors"]) == 0


class TestHardValidations:
    def test_missing_stop_loss_fails(self):
        """Omitting stop_loss should make the order invalid."""
        order = _valid_buy_order()
        order["stop_loss"] = None
        result = validate_order(order)
        assert result["valid"] is False
        assert any("stop_loss" in e for e in result["errors"])

    def test_invalid_ticker_fails(self):
        """A ticker with invalid characters should fail."""
        order = _valid_buy_order()
        order["ticker"] = "invalid ticker!"
        result = validate_order(order)
        assert result["valid"] is False
        assert any("ticker" in e.lower() or "Invalid" in e for e in result["errors"])

    def test_buy_stop_loss_above_price_fails(self):
        """For a BUY, stop_loss above current_price should fail."""
        order = _valid_buy_order()
        order["stop_loss"] = 160.0  # Above current_price of 150
        result = validate_order(order)
        assert result["valid"] is False
        assert any("stop_loss" in e for e in result["errors"])

    def test_limit_order_without_price_fails(self):
        """A LIMIT order without limit_price should fail."""
        order = _valid_buy_order()
        order["order_type"] = "LIMIT"
        order["limit_price"] = None
        result = validate_order(order)
        assert result["valid"] is False
        assert any("limit_price" in e for e in result["errors"])


class TestSoftWarnings:
    def test_large_stop_distance_warns(self):
        """Stop-loss > 10% from price should produce a warning."""
        order = _valid_buy_order()
        order["stop_loss"] = 120.0  # 20% below 150
        result = validate_order(order)
        assert result["valid"] is True  # Still valid
        assert len(result["warnings"]) > 0

    def test_large_order_value_warns(self):
        """Order value > $100k should produce a warning."""
        order = _valid_buy_order()
        order["quantity"] = 1000  # 1000 * 150 = $150k
        result = validate_order(order)
        assert result["valid"] is True
        assert any("Large order" in w or "100,000" in w for w in result["warnings"])
