from pathlib import Path

import numpy as np
import pandas as pd

from src.core.backtester import EnhancedBacktester
from src.utils import load_config

REQUIRED_KEYS = {
    "status",
    "message",
    "sharpe_ratio",
    "information_coefficient",
    "ic_1d",
    "ic_5d",
    "ic_21d",
    "ic_63d",
    "annualized_return",
    "max_drawdown",
    "daily_turnover",
    "alpha_vs_spy",
    "spy_sharpe",
    "spy_annual_return",
    "xgb_sharpe",
    "logreg_sharpe",
    "universe_size",
    "delisted_count",
    "train_start",
    "train_end",
    "test_start",
    "test_end",
}


def _synthetic_panel() -> pd.DataFrame:
    dates = pd.bdate_range("2020-01-01", periods=180)
    tickers = ["AAPL", "MSFT", "JPM", "BBBY", "XOM"]

    tuples = []
    rows = []
    for ticker in tickers:
        base = np.linspace(50, 100, len(dates)) + np.random.default_rng(42).normal(0, 1, len(dates))
        if ticker == "BBBY":
            base[-30:] = np.nan
        for i, dt in enumerate(dates):
            close = base[i]
            open_px = close * 0.99 if np.isfinite(close) else np.nan
            high = close * 1.01 if np.isfinite(close) else np.nan
            low = close * 0.98 if np.isfinite(close) else np.nan
            vol = 1_000_000 if np.isfinite(close) else np.nan
            tuples.append((dt, ticker))
            rows.append([open_px, high, low, close, vol])

    return pd.DataFrame(
        rows,
        index=pd.MultiIndex.from_tuples(tuples, names=["date", "ticker"]),
        columns=["Open", "High", "Low", "Close", "Volume"],
    )


def _patch_dependencies(monkeypatch):
    monkeypatch.setattr("src.prepare.DataLoader.load", lambda self, start, end: _synthetic_panel())
    monkeypatch.setattr(
        "src.benchmark.SPYBenchmark.run",
        lambda self: {
            "sharpe_ratio": 0.5,
            "annualized_return": 0.08,
            "max_drawdown": -0.2,
            "returns_series": pd.Series(dtype=float),
        },
    )
    monkeypatch.setattr(
        "src.ml_baseline.MLBaseline.run",
        lambda self: {
            "xgb_sharpe": 0.3,
            "logreg_sharpe": 0.2,
            "xgb_annual_return": 0.05,
            "logreg_annual_return": 0.04,
        },
    )


def test_run_returns_success_dict_with_all_fields(monkeypatch):
    _patch_dependencies(monkeypatch)
    result = EnhancedBacktester(load_config("config/settings.yaml")).run()

    assert isinstance(result, dict)
    assert result["status"] == "success"
    assert REQUIRED_KEYS.issubset(result.keys())


def test_run_handles_syntax_error_gracefully(monkeypatch):
    _patch_dependencies(monkeypatch)
    factor_path = Path("sandbox/factor.py")
    original = factor_path.read_text(encoding="utf-8")
    try:
        factor_path.write_text("def generate_signals(", encoding="utf-8")
        result = EnhancedBacktester(load_config("config/settings.yaml")).run()
        assert result["status"] == "error"
        assert isinstance(result.get("message"), str)
        assert len(result["message"]) > 0
    finally:
        factor_path.write_text(original, encoding="utf-8")


def test_run_handles_runtime_error_gracefully(monkeypatch):
    _patch_dependencies(monkeypatch)
    factor_path = Path("sandbox/factor.py")
    original = factor_path.read_text(encoding="utf-8")
    try:
        factor_path.write_text(
            "import pandas as pd\n"
            "def generate_signals(data: pd.DataFrame) -> pd.Series:\n"
            "    return 1 / 0\n",
            encoding="utf-8",
        )
        result = EnhancedBacktester(load_config("config/settings.yaml")).run()
        assert result["status"] == "error"
    finally:
        factor_path.write_text(original, encoding="utf-8")
