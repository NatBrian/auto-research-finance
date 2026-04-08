import json
import logging
import os
import ssl
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml


class DataUnavailableError(Exception):
    """Raised when market data cannot be downloaded."""


@lru_cache(maxsize=1)
def load_config(path: str = "config/settings.yaml") -> dict:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def get_ssl_verify() -> bool:
    """Get SSL verification setting from config."""
    config = load_config()
    return config.get("network", {}).get("ssl_verify", True)


def create_ssl_context() -> ssl.SSLContext | None:
    """Create SSL context based on config settings."""
    if not get_ssl_verify():
        # Create unverified context for proxy/corporate networks
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    return None


_ssl_patched = False


def install_ssl_patch() -> None:
    """Install SSL patch to disable verification globally if configured."""
    global _ssl_patched
    if _ssl_patched:
        return

    if not get_ssl_verify():
        # Disable urllib3 warnings
        try:
            import urllib3
            urllib3.disable_warnings()
        except ImportError:
            pass

        # Set environment variables for curl-based requests
        os.environ["CURL_CA_BUNDLE"] = ""
        os.environ["REQUESTS_CA_BUNDLE"] = ""
        os.environ["SSL_CERT_FILE"] = ""

        # Patch curl_cffi (used by yfinance) to disable SSL verification
        try:
            import curl_cffi.requests
            original_init = curl_cffi.requests.Session.__init__
            def patched_init(self, *args, **kwargs):
                kwargs['verify'] = False
                original_init(self, *args, **kwargs)
            curl_cffi.requests.Session.__init__ = patched_init
        except ImportError:
            pass

        # Create unverified SSL context
        ssl_context = create_ssl_context()
        if ssl_context:
            # Patch urllib for standard library
            https_handler = urllib.request.HTTPSHandler(context=ssl_context)
            opener = urllib.request.build_opener(https_handler)
            urllib.request.install_opener(opener)

        # Patch requests library if available
        try:
            import requests
            original_request = requests.Session.request
            def patched_request(self, *args, **kwargs):
                kwargs['verify'] = False
                return original_request(self, *args, **kwargs)
            requests.Session.request = patched_request
        except ImportError:
            pass

    _ssl_patched = True


def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("paper_to_factor")
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level.upper())
    return logger


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.floating,)):
        value = float(value)
        return value if np.isfinite(value) else None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, (np.ndarray,)):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _sanitize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _sanitize_json(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_sanitize_json(item) for item in value.tolist()]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        value = float(value)
        return value if np.isfinite(value) else None
    return value


def safe_json_dumps(obj: Any) -> str:
    return json.dumps(_sanitize_json(obj), default=_json_default, allow_nan=False)
