"""
TradingAgents-CC — Order Validator

Pre-submission sanity checks for trading orders.
Returns a validation result dict with hard errors and soft warnings.
"""

import re
from typing import Any


def validate_order(order: dict[str, Any]) -> dict[str, Any]:
    """Validate a trading order before submission.

    Parameters
    ----------
    order : dict
        Order dictionary with keys: ticker, action, quantity, order_type,
        limit_price, stop_loss, take_profit, current_price, etc.

    Returns
    -------
    dict
        ``{"valid": bool, "errors": [str], "warnings": [str]}``
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ------------------------------------------------------------------
    # Hard validations (any failure -> valid = False)
    # ------------------------------------------------------------------

    # Action
    action = order.get("action", "")
    if action not in ("BUY", "SELL"):
        errors.append(f"Invalid action '{action}'. Must be 'BUY' or 'SELL'.")

    # Quantity
    quantity = order.get("quantity")
    if quantity is None:
        errors.append("Quantity is required.")
    else:
        try:
            quantity = int(quantity)
            if quantity <= 0:
                errors.append(f"Quantity must be a positive integer, got {quantity}.")
        except (TypeError, ValueError):
            errors.append(f"Quantity must be a positive integer, got '{quantity}'.")

    # Ticker format
    ticker = order.get("ticker", "")
    if not re.match(r"^[A-Z]{1,5}(-[A-Z])?$", str(ticker)):
        errors.append(
            f"Invalid ticker '{ticker}'. Must match pattern [A-Z]{{1,5}}(-[A-Z])?."
        )

    # Stop-loss
    stop_loss = order.get("stop_loss")
    if stop_loss is None or stop_loss == 0:
        errors.append("stop_loss must be set and > 0.")
    else:
        try:
            stop_loss = float(stop_loss)
            if stop_loss <= 0:
                errors.append(f"stop_loss must be > 0, got {stop_loss}.")
        except (TypeError, ValueError):
            errors.append(f"stop_loss must be a number, got '{stop_loss}'.")

    # Stop-loss side validation (requires current_price)
    current_price = order.get("current_price")
    if current_price and stop_loss and isinstance(stop_loss, (int, float)):
        current_price = float(current_price)
        if action == "BUY" and stop_loss >= current_price:
            errors.append(
                f"For a BUY order, stop_loss ({stop_loss}) must be below "
                f"current_price ({current_price})."
            )
        elif action == "SELL" and stop_loss <= current_price:
            errors.append(
                f"For a SELL order, stop_loss ({stop_loss}) must be above "
                f"current_price ({current_price})."
            )

    # Order type
    order_type = order.get("order_type", "")
    if order_type not in ("MARKET", "LIMIT"):
        errors.append(f"Invalid order_type '{order_type}'. Must be 'MARKET' or 'LIMIT'.")

    # Limit price for LIMIT orders
    if order_type == "LIMIT":
        limit_price = order.get("limit_price")
        if limit_price is None:
            errors.append("limit_price is required for LIMIT orders.")
        else:
            try:
                limit_price = float(limit_price)
                if limit_price <= 0:
                    errors.append(f"limit_price must be > 0, got {limit_price}.")
            except (TypeError, ValueError):
                errors.append(f"limit_price must be a number, got '{limit_price}'.")

    # ------------------------------------------------------------------
    # Soft warnings (valid = True but noteworthy)
    # ------------------------------------------------------------------

    if (
        current_price
        and stop_loss
        and isinstance(stop_loss, (int, float))
        and isinstance(current_price, (int, float))
    ):
        distance_pct = abs(current_price - stop_loss) / current_price * 100
        if distance_pct > 10:
            warnings.append(
                f"Stop-loss distance is {distance_pct:.1f}% from current price "
                f"(> 10% threshold)."
            )

    if (
        quantity
        and current_price
        and isinstance(quantity, (int, float))
        and isinstance(current_price, (int, float))
    ):
        order_value = int(quantity) * float(current_price)
        if order_value > 100_000:
            warnings.append(
                f"Large order value: ${order_value:,.2f} "
                f"({int(quantity)} x ${float(current_price):,.2f})."
            )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
