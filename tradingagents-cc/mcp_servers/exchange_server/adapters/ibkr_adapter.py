"""
TradingAgents-CC — Interactive Brokers Adapter

Wraps the ib_insync library to provide trading via IB Gateway or TWS.
Raises ConfigurationError when connection cannot be established.
"""

import os
from typing import Any

from src.utils import ConfigurationError, setup_logging

logger = setup_logging()


class IBKRAdapter:
    """Interactive Brokers exchange adapter using ib_insync."""

    def __init__(self, config: dict) -> None:
        ibkr_cfg = config.get("exchange", {}).get("ibkr", {})
        host = os.environ.get("IB_HOST", ibkr_cfg.get("host", "127.0.0.1"))
        port = int(os.environ.get("IB_PORT", ibkr_cfg.get("port", 7497)))
        client_id = int(os.environ.get("IB_CLIENT_ID", ibkr_cfg.get("client_id", 1)))

        try:
            from ib_insync import IB  # type: ignore
            self._ib = IB()
            self._ib.connect(host, port, clientId=client_id)
            logger.info("IBKR adapter connected to %s:%s (clientId=%s)", host, port, client_id)
        except Exception as exc:
            raise ConfigurationError(
                f"Failed to connect to IB Gateway/TWS at {host}:{port} "
                f"(clientId={client_id}). Ensure IB Gateway or TWS is running "
                f"with API connections enabled.\n"
                f"Error: {exc}"
            ) from exc

    def __del__(self) -> None:
        self.disconnect()

    def disconnect(self) -> None:
        """Disconnect from IB Gateway/TWS."""
        try:
            if hasattr(self, "_ib") and self._ib.isConnected():
                self._ib.disconnect()
                logger.info("IBKR adapter disconnected")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_portfolio_summary(self) -> dict[str, Any]:
        """Return portfolio summary from IB account."""
        try:
            from ib_insync import util  # type: ignore

            account_values = self._ib.accountSummary()
            portfolio_value = 0.0
            cash = 0.0
            for av in account_values:
                if av.tag == "NetLiquidation":
                    portfolio_value = float(av.value)
                elif av.tag == "TotalCashValue":
                    cash = float(av.value)

            positions = self._ib.positions()
            pos_list = []
            for p in positions:
                pos_list.append({
                    "ticker": p.contract.symbol,
                    "quantity": int(p.position),
                    "avg_price": float(p.avgCost) / max(1, abs(int(p.position))),
                    "current_value": float(p.position) * float(p.marketPrice)
                    if hasattr(p, "marketPrice")
                    else 0.0,
                    "unrealized_pnl": float(p.unrealizedPNL)
                    if hasattr(p, "unrealizedPNL")
                    else 0.0,
                })

            return {
                "portfolio_value": portfolio_value,
                "cash": cash,
                "positions": pos_list,
                "day_pnl": 0.0,
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def get_current_positions(self) -> list[dict[str, Any]]:
        """Return list of open positions."""
        try:
            positions = self._ib.positions()
            return [
                {
                    "ticker": p.contract.symbol,
                    "quantity": int(p.position),
                    "avg_price": float(p.avgCost) / max(1, abs(int(p.position))),
                    "current_value": 0.0,
                    "unrealized_pnl": 0.0,
                }
                for p in positions
            ]
        except Exception as exc:
            return [{"status": "error", "message": str(exc)}]

    def submit_order(self, order: dict[str, Any]) -> dict[str, Any]:
        """Submit an order to Interactive Brokers."""
        try:
            from ib_insync import Stock, MarketOrder, LimitOrder  # type: ignore

            contract = Stock(order["ticker"], "SMART", "USD")
            self._ib.qualifyContracts(contract)

            action = order["action"]
            quantity = int(order["quantity"])
            order_type = order.get("order_type", "MARKET")

            if order_type == "LIMIT":
                ib_order = LimitOrder(action, quantity, float(order["limit_price"]))
            else:
                ib_order = MarketOrder(action, quantity)

            trade = self._ib.placeOrder(contract, ib_order)
            self._ib.sleep(1)  # Allow fill processing

            return {
                "order_id": str(trade.order.orderId),
                "status": trade.orderStatus.status,
                "filled_price": float(trade.orderStatus.avgFillPrice)
                if trade.orderStatus.avgFillPrice
                else None,
                "filled_quantity": int(trade.orderStatus.filled)
                if trade.orderStatus.filled
                else 0,
                "timestamp": str(trade.log[-1].time) if trade.log else "",
                "exchange_message": f"IBKR order {trade.order.orderId} — {trade.orderStatus.status}",
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an order on IB."""
        try:
            open_orders = self._ib.openOrders()
            for o in open_orders:
                if str(o.orderId) == order_id:
                    self._ib.cancelOrder(o)
                    return {"status": "CANCELLED", "order_id": order_id}
            return {"status": "error", "message": f"Order {order_id} not found"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def get_order_status(self, order_id: str) -> dict[str, Any]:
        """Get the status of an IB order."""
        try:
            trades = self._ib.trades()
            for t in trades:
                if str(t.order.orderId) == order_id:
                    return {
                        "order_id": order_id,
                        "status": t.orderStatus.status,
                        "filled_price": float(t.orderStatus.avgFillPrice)
                        if t.orderStatus.avgFillPrice
                        else None,
                        "filled_quantity": int(t.orderStatus.filled)
                        if t.orderStatus.filled
                        else 0,
                    }
            return {"status": "error", "message": f"Order {order_id} not found"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)}
