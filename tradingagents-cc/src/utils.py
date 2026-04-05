"""
TradingAgents-CC Shared Utilities

Provides common helpers used across the entire project:
  - Custom exceptions
  - Configuration loading (YAML)
  - Logging setup
  - JSON serialization for numpy / pandas objects
  - Path and formatting helpers
"""

import json
import logging
import math
from datetime import datetime, date
from pathlib import Path
from functools import lru_cache
from typing import Any

import yaml
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------

class DataUnavailableError(Exception):
    """Raised when a data source cannot provide the requested data."""
    pass


class ConfigurationError(Exception):
    """Raised when required configuration or credentials are missing."""
    pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_config(path: str | None = None) -> dict:
    """Load and cache the YAML configuration file.

    Parameters
    ----------
    path : str, optional
        Absolute or relative path to `settings.yaml`.  When *None* the
        default location ``config/settings.yaml`` relative to the project
        root is used.

    Returns
    -------
    dict
        Parsed configuration dictionary.
    """
    if path is None:
        path = str(get_project_root() / "config" / "settings.yaml")
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(level: str = "INFO") -> logging.Logger:
    """Return a pre-configured logger named ``tradingagents_cc``.

    Parameters
    ----------
    level : str
        Logging level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).

    Returns
    -------
    logging.Logger
    """
    logger = logging.getLogger("tradingagents_cc")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


# ---------------------------------------------------------------------------
# JSON Serialization
# ---------------------------------------------------------------------------

class _SafeEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy, pandas, and other non-native types."""

    def default(self, obj: Any) -> Any:  # noqa: ANN401
        # numpy scalar types
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            if math.isnan(obj) or math.isinf(obj):
                return None
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        # pandas types
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        if isinstance(obj, pd.DataFrame):
            return obj.reset_index().to_dict(orient="records")
        if isinstance(obj, pd.Series):
            return obj.to_dict()
        # standard‐lib datetime
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        # NaT / NaN
        if obj is pd.NaT:
            return None
        # Let the base class raise TypeError for truly unsupported types
        return super().default(obj)


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """Serialize *obj* to a JSON string, handling numpy / pandas types.

    Parameters
    ----------
    obj : Any
        Python object to serialize.
    **kwargs
        Forwarded to ``json.dumps``.

    Returns
    -------
    str
        JSON string.
    """
    kwargs.setdefault("indent", 2)
    kwargs.setdefault("ensure_ascii", False)
    return json.dumps(obj, cls=_SafeEncoder, **kwargs)


# ---------------------------------------------------------------------------
# Path Helpers
# ---------------------------------------------------------------------------

def get_project_root() -> Path:
    """Return the project root directory.

    Assumes this file lives at ``<root>/src/utils.py``.
    """
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Formatting Helpers
# ---------------------------------------------------------------------------

def format_currency(value: float) -> str:
    """Format a numeric value as US-dollar currency string.

    Examples
    --------
    >>> format_currency(1234.5)
    '$1,234.50'
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "$0.00"
    return f"${value:,.2f}"


def compute_percentage_change(old: float, new: float) -> float:
    """Compute percentage change from *old* to *new*.

    Returns 0.0 when *old* is zero to avoid ``ZeroDivisionError``.
    """
    if old is None or new is None:
        return 0.0
    try:
        if old == 0:
            return 0.0
        return ((new - old) / abs(old)) * 100.0
    except (TypeError, ZeroDivisionError):
        return 0.0
