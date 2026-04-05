"""
TradingAgents-CC — Alpaca Brokerage Adapter

Wraps the alpaca-trade-api library to provide real/paper trading
via Alpaca Markets.  Raises ConfigurationError when required
environment variables are not set.
"""

import os
from typing import Any

from src.utils import ConfigurationError, setup_logging

logger = setup_logging()


class AlpacaAdapter:
    """Alpaca Markets exchange adapter."""

    def __init__(self, config: dict) -> None:
        api_key = os.environ.get("ALPACA_API_KEY")
        secret_key = os.environ.get("ALPACA_SECRET_KEY")
        base_url = os.environ.get(
            "ALPACA_BASE_URL",
            config.get("exchange", {}).get("alpaca", {}).get(
                "base_url", "https://paper-api.alpaca.markets"
            ),
        )

        if not api_key or not secret_key:
            raise ConfigurationError(
                "Alpaca credentials not found. Set environment variables:\n"
                "  ALPACA_API_KEY=your_key\n"
                "  ALPACA_SECRET_KEY=your_secret\n"
                "  ALPACA_BASE_URL=https://paper-api.alpaca.markets  (optional)"
            )

        try:
            import alpaca_trade_api as tradeapi  # type: ignore
            self._api = tradeapi.REST(api_key, secret_key, base_url, api_version="v2")
            logger.info("Alpaca adapter connected to %s", base_url)
        except Exception as exc:
            raise ConfigurationError(
                f"Failed to initialize Alpaca REST client: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_portfolio_summary(self) -> dict[str, Any]:
        """Return portfolio summary from Alpaca account."""
        try:
            account = self._api.get_account()
            positions = self._api.list_positions()
            return {
                "portfolio_value": float(account.portfolio_value),
                "cash": float(account.cash),
                "positions": [
                    {
                        "ticker": p.symbol,
                        "quantity": int(p.qty),
                        "avg_price": float(p.avg_entry_price),
                        "current_value": float(p.market_value),
                        "unrealized_pnl": float(p.unrealized_pl),
                    }
                    for p in positions
                ],
                "day_pnl": float(getattr(account, "equity", 0))
                - float(getattr(account, "last_equity", 0)),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def get_current_positions(self) -> list[dict[str, Any]]:
        """Return list of open positions."""
        try:
            positions = self._api.list_positions()
            return [
                {
                    "ticker": p.symbol,
                    "quantity": int(p.qty),
                    "avg_price": float(p.avg_entry_price),
                    "current_value": float(p.market_value),
                    "unrealized_pnl": float(p.unrealized_pl),
                }
                for p in positions
            ]
        except Exception as exc:
            return [{"status": "error", "message": str(exc)}]

    def submit_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """Submit an order to Alpaca."""
        try:
            side = "buy" if order["action"] == "BUY" else "sell"
            order_type = order.get("order_type", "MARKET").lower()
            limit_price = order.get("limit_price")

            kwargs: dict[str, Any] = {
                "symbol": order["ticker"],
                "qty": int(order["quantity"]),
                "side": side,
                "type": order_type,
                "time_in_force": order.get("time_in_force", "day").lower(),
            }
            if order_type == "limit" and limit_price is not None:
                kwargs["limit_price"] = float(limit_price)

            result = self._api.submit_order(**kwargs)

            return {
                "order_id": result.id,
                "status": result.status,
                "filled_price": float(result.filled_avg_price)
                if result.filled_avg_price
                else None,
                "filled_quantity": int(result.filled_qty) if result.filled_qty else 0,
                "timestamp": str(result.submitted_at),
                "exchange_message": f"Alpaca order {result.id} — {result.status}",
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an order on Alpaca."""
        try:
            self._api.cancel_order(order_id)
            return {"status": "CANCELLED", "order_id": order_id}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Get the status of an Alpaca order."""
        try:
            o = self._api.get_order(order_id)
            return {
                "order_id": o.id,
                "status": o.status,
                "filled_price": float(o.filled_avg_price)
                if o.filled_avg_price
                else None,
                "filled_quantity": int(o.filled_qty) if o.filled_qty else 0,
                "timestamp": str(o.submitted_at),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
