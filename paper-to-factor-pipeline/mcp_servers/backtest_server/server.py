import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import traceback
from mcp.server.fastmcp import FastMCP

from src.core.backtester import EnhancedBacktester
from src.utils import load_config, safe_json_dumps


mcp = FastMCP("backtest-server", json_response=True)


@mcp.tool()
def ping_backtest() -> dict:
    return {"status": "ok", "message": "backtest MCP server is running"}


@mcp.tool()
def run_backtest() -> str:
    try:
        config = load_config("config/settings.yaml")
        result = EnhancedBacktester(config).run()
        return safe_json_dumps(result)
    except Exception:
        return safe_json_dumps(
            {
                "status": "error",
                "message": "MCP server internal error: " + traceback.format_exc(),
            }
        )


if __name__ == "__main__":
    mcp.run(transport="stdio")
