"""
TradingAgents-CC — Paper Trading Adapter

Simulates a brokerage using a local JSON file for portfolio state.
Supports market and limit orders with configurable slippage.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf
from curl_cffi.requests import Session

from src.utils import get_project_root, load_config, setup_logging

logger = setup_logging()


def _get_ssl_verify() -> bool:
    """Read SSL verify setting from config. Defaults to True for security."""
    try:
        config = load_config()
        return config.get("ssl", {}).get("verify", True)
    except Exception:
        return True


_SSL_VERIFY = _get_ssl_verify()
_SSL_SESSION = Session(verify=_SSL_VERIFY)


class PaperAdapter:
    """Simulated paper-trading exchange adapter."""

    def __init__(self, config: dict) -> None:
        paper_cfg = config.get("exchange", {}).get("paper", {})
        self._initial_cash = float(paper_cfg.get("initial_cash", 100_000.0))
        self._slippage_bps = int(paper_cfg.get("slippage_bps", 5))

        data_cfg = config.get("data", {})
        portfolio_path = data_cfg.get(
            "paper_portfolio_path", "data/paper_portfolio.json"
        )
        self._portfolio_path = get_project_root() / portfolio_path
        self._portfolio = self._load_or_init()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_portfolio_summary(self) -> dict[str, Any]:
        """Return portfolio value, cash, positions, and day P&L."""
        self._refresh_market_values()
        positions = self._portfolio.get("positions", {})
        total_position_value = sum(
            p.get("current_value", 0) for p in positions.values()
        )
        cash = self._portfolio.get("cash", 0)
        portfolio_value = cash + total_position_value

        return {
            "portfolio_value": round(portfolio_value, 2),
            "cash": round(cash, 2),
            "positions": [
                {
                    "ticker": ticker,
                    "quantity": p["quantity"],
                    "avg_price": round(p["avg_price"], 2),
                    "current_value": round(p.get("current_value", 0), 2),
                    "unrealized_pnl": round(
                        p.get("current_value", 0) - p["quantity"] * p["avg_price"], 2
                    ),
                }
                for ticker, p in positions.items()
                if p["quantity"] > 0
            ],
            "day_pnl": 0.0,  # Simplified — no intraday tracking
        }

    def get_current_positions(self) -> list[dict[str, Any]]:
        """Return list of open positions."""
        self._refresh_market_values()
        positions = self._portfolio.get("positions", {})
        return [
            {
                "ticker": ticker,
                "quantity": p["quantity"],
                "avg_price": round(p["avg_price"], 2),
                "current_value": round(p.get("current_value", 0), 2),
                "unrealized_pnl": round(
                    p.get("current_value", 0) - p["quantity"] * p["avg_price"], 2
                ),
            }
            for ticker, p in positions.items()
            if p["quantity"] > 0
        ]

    def submit_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """Execute a paper trade order."""
        ticker = order["ticker"]
        action = order["action"]
        quantity = int(order["quantity"])
        order_type = order.get("order_type", "MARKET")
        limit_price = order.get("limit_price")

        # Get current market price
        try:
            info = yf.Ticker(ticker, session=_SSL_SESSION).info
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
            if current_price is None:
                hist = yf.download(ticker, period="1d", progress=False, session=_SSL_SESSION)
                if hist is not None and not hist.empty:
                    current_price = float(hist["Close"].iloc[-1])
        except Exception as exc:
            # Fallback: try without session (some environments work differently)
            try:
                hist = yf.download(ticker, period="5d", progress=False)
                if hist is not None and not hist.empty:
                    current_price = float(hist["Close"].iloc[-1])
                else:
                    return {
                        "status": "error",
                        "message": f"Cannot get current price for {ticker}: {exc}",
                    }
            except Exception as exc2:
                return {
                    "status": "error",
                    "message": f"Cannot get current price for {ticker}: {exc2}",
                }

        if current_price is None:
            return {"status": "error", "message": f"No price available for {ticker}"}

        current_price = float(current_price)

        # Handle limit orders
        if order_type == "LIMIT" and limit_price is not None:
            limit_price = float(limit_price)
            if action == "BUY" and current_price > limit_price:
                # Price hasn't reached limit — add to pending
                order_id = f"PAPER_{ticker}_{int(time.time())}"
                pending_order = {
                    "order_id": order_id,
                    "ticker": ticker,
                    "action": action,
                    "quantity": quantity,
                    "order_type": "LIMIT",
                    "limit_price": limit_price,
                    "status": "PENDING",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                self._portfolio.setdefault("pending_orders", []).append(pending_order)
                self._save()
                return {
                    "order_id": order_id,
                    "status": "PENDING",
                    "message": f"Limit order placed. Current price ${current_price:.2f} > limit ${limit_price:.2f}",
                    "filled_price": None,
                    "filled_quantity": 0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "exchange_message": "Paper limit order queued",
                }

        # Apply slippage for market orders
        slippage_mult = self._slippage_bps / 10000.0
        if action == "BUY":
            fill_price = current_price * (1 + slippage_mult)
        else:
            fill_price = current_price * (1 - slippage_mult)

        fill_price = round(fill_price, 2)
        order_id = f"PAPER_{ticker}_{int(time.time())}"
        total_cost = fill_price * quantity

        positions = self._portfolio.setdefault("positions", {})

        if action == "BUY":
            if self._portfolio["cash"] < total_cost:
                return {
                    "status": "error",
                    "message": (
                        f"Insufficient cash. Need ${total_cost:,.2f}, "
                        f"have ${self._portfolio['cash']:,.2f}"
                    ),
                }
            self._portfolio["cash"] -= total_cost

            if ticker in positions:
                pos = positions[ticker]
                old_total = pos["quantity"] * pos["avg_price"]
                new_total = old_total + total_cost
                pos["quantity"] += quantity
                pos["avg_price"] = new_total / pos["quantity"]
            else:
                positions[ticker] = {
                    "quantity": quantity,
                    "avg_price": fill_price,
                    "current_value": total_cost,
                }

        elif action == "SELL":
            if ticker not in positions or positions[ticker]["quantity"] < quantity:
                avail = positions.get(ticker, {}).get("quantity", 0)
                return {
                    "status": "error",
                    "message": (
                        f"Insufficient shares. Want to sell {quantity}, "
                        f"have {avail}"
                    ),
                }
            self._portfolio["cash"] += total_cost
            positions[ticker]["quantity"] -= quantity
            if positions[ticker]["quantity"] == 0:
                del positions[ticker]

        # Log the trade
        trade_entry = {
            "order_id": order_id,
            "ticker": ticker,
            "action": action,
            "quantity": quantity,
            "fill_price": fill_price,
            "total_value": total_cost,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._portfolio.setdefault("trade_log", []).append(trade_entry)
        self._portfolio.setdefault("orders", []).append({
            **trade_entry,
            "status": "FILLED",
            "order_type": order_type,
        })

        self._save()

        return {
            "order_id": order_id,
            "status": "FILLED",
            "filled_price": fill_price,
            "filled_quantity": quantity,
            "timestamp": trade_entry["timestamp"],
            "exchange_message": f"Paper {action} executed at ${fill_price:.2f}",
        }

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel a pending limit order."""
        pending = self._portfolio.get("pending_orders", [])
        for i, o in enumerate(pending):
            if o["order_id"] == order_id:
                pending.pop(i)
                self._save()
                return {"status": "CANCELLED", "order_id": order_id}
        return {"status": "error", "message": f"Order {order_id} not found"}

    def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Look up an order by ID."""
        for o in self._portfolio.get("orders", []):
            if o["order_id"] == order_id:
                return o
        for o in self._portfolio.get("pending_orders", []):
            if o["order_id"] == order_id:
                return o
        return {"status": "error", "message": f"Order {order_id} not found"}

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _load_or_init(self) -> dict:
        """Load existing portfolio or initialize a new one."""
        if self._portfolio_path.exists():
            try:
                with open(self._portfolio_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                logger.warning("Corrupt portfolio file — reinitializing")

        portfolio = {
            "cash": self._initial_cash,
            "positions": {},
            "orders": [],
            "pending_orders": [],
            "trade_log": [],
        }
        self._portfolio_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._portfolio_path, "w", encoding="utf-8") as f:
            json.dump(portfolio, f, indent=2)
        logger.info(
            "Initialized paper portfolio with $%s cash at %s",
            f"{self._initial_cash:,.2f}",
            self._portfolio_path,
        )
        return portfolio

    def _save(self) -> None:
        """Persist portfolio to JSON."""
        self._portfolio_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._portfolio_path, "w", encoding="utf-8") as f:
            json.dump(self._portfolio, f, indent=2)

    def _refresh_market_values(self) -> None:
        """Update current_value for all positions using live prices."""
        positions = self._portfolio.get("positions", {})
        for ticker, pos in positions.items():
            try:
                info = yf.Ticker(ticker, session=_SSL_SESSION).info
                price = info.get("currentPrice") or info.get("regularMarketPrice")
                if price:
                    pos["current_value"] = round(float(price) * pos["quantity"], 2)
            except Exception:
                # Fallback: try without session
                try:
                    hist = yf.download(ticker, period="1d", progress=False)
                    if hist is not None and not hist.empty:
                        price = float(hist["Close"].iloc[-1])
                        pos["current_value"] = round(price * pos["quantity"], 2)
                    else:
                        pos["current_value"] = pos["quantity"] * pos["avg_price"]
                except Exception:
                    pos["current_value"] = pos["quantity"] * pos["avg_price"]
