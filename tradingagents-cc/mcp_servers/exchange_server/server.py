"""
TradingAgents-CC — Exchange MCP Server

Provides tools for portfolio management and order submission.
Uses an adapter pattern to support paper trading, Alpaca, and IBKR.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
from mcp.server.fastmcp import FastMCP

from src.utils import load_config, safe_json_dumps, setup_logging
from src.order_validator import validate_order

logger = setup_logging()
mcp = FastMCP("exchange")

# --- Load exchange adapter from config ---
config = load_config()
adapter_name = config.get("exchange", {}).get("default_adapter", "paper")

if adapter_name == "paper":
    from mcp_servers.exchange_server.adapters.paper_adapter import PaperAdapter
    exchange = PaperAdapter(config)
elif adapter_name == "alpaca":
    from mcp_servers.exchange_server.adapters.alpaca_adapter import AlpacaAdapter
    exchange = AlpacaAdapter(config)
elif adapter_name == "ibkr":
    from mcp_servers.exchange_server.adapters.ibkr_adapter import IBKRAdapter
    exchange = IBKRAdapter(config)
else:
    raise ValueError(f"Unknown exchange adapter: {adapter_name}")

logger.info("Exchange server loaded adapter: %s", adapter_name)


# ------------------------------------------------------------------
# Health Check
# ------------------------------------------------------------------

@mcp.tool()
def ping_exchange() -> str:
    """Health check for the exchange MCP server."""
    return json.dumps({
        "status": "ok",
        "adapter": adapter_name,
        "message": "exchange MCP server running",
    })


# ------------------------------------------------------------------
# Portfolio
# ------------------------------------------------------------------

@mcp.tool()
def get_portfolio_summary() -> str:
    """Get current portfolio summary (value, cash, positions, P&L)."""
    try:
        data = exchange.get_portfolio_summary()
        return safe_json_dumps(data)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def get_current_positions() -> str:
    """Get list of current open positions."""
    try:
        data = exchange.get_current_positions()
        return safe_json_dumps(data)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ------------------------------------------------------------------
# Order Management
# ------------------------------------------------------------------

@mcp.tool()
def submit_order(order_json: str) -> str:
    """Submit a trading order. Pass the full order as a JSON string.

    The order is validated before submission. If validation fails,
    the order is rejected and no trade is executed.
    """
    try:
        order = json.loads(order_json)
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "message": f"Invalid JSON: {e}"})

    # Validate first
    validation = validate_order(order)
    if not validation["valid"]:
        return json.dumps({
            "status": "error",
            "message": "Order validation failed",
            "errors": validation["errors"],
        })

    # Log warnings if any
    if validation["warnings"]:
        for w in validation["warnings"]:
            logger.warning("Order warning: %s", w)

    # Submit to exchange
    try:
        result = exchange.submit_order(order)
        return safe_json_dumps(result)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def cancel_order(order_id: str) -> str:
    """Cancel a pending order by order ID."""
    try:
        result = exchange.cancel_order(order_id)
        return safe_json_dumps(result)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


@mcp.tool()
def get_order_status(order_id: str) -> str:
    """Get the status of an order by order ID."""
    try:
        result = exchange.get_order_status(order_id)
        return safe_json_dumps(result)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting Exchange MCP server (adapter=%s)...", adapter_name)
    mcp.run(transport="stdio")
