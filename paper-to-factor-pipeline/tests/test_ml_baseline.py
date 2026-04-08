from __future__ import annotations

import inspect

import numpy as np
import pandas as pd

from src.ml_baseline import MLBaseline


def _make_data(start: str, periods: int, tickers: list[str]) -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=periods)
    tuples = []
    rows = []

    for i, ticker in enumerate(tickers):
        rng = np.random.default_rng(100 + i)
        close = 100 + np.cumsum(rng.normal(0.1, 1.0, len(dates)))
        volume = rng.integers(500_000, 2_000_000, len(dates)).astype(float)

        for j, dt in enumerate(dates):
            c = close[j]
            tuples.append((dt, ticker))
            rows.append([c * 0.99, c * 1.01, c * 0.98, c, volume[j]])

    return pd.DataFrame(
        rows,
        index=pd.MultiIndex.from_tuples(tuples, names=["date", "ticker"]),
        columns=["Open", "High", "Low", "Close", "Volume"],
    )


def test_ml_baseline_returns_dict_with_sharpe_keys():
    train = _make_data("2020-01-01", 180, ["AAPL", "MSFT", "JPM", "XOM", "PG"])
    test = _make_data("2021-01-01", 120, ["AAPL", "MSFT", "JPM", "XOM", "PG"])

    result = MLBaseline(train, test).run()
    assert "xgb_sharpe" in result
    assert "logreg_sharpe" in result
    assert "xgb_annual_return" in result
    assert "logreg_annual_return" in result
    assert isinstance(result["xgb_sharpe"], float) or np.isnan(result["xgb_sharpe"])
    assert isinstance(result["logreg_sharpe"], float) or np.isnan(result["logreg_sharpe"])
    assert isinstance(result["xgb_annual_return"], float) or np.isnan(result["xgb_annual_return"])
    assert isinstance(result["logreg_annual_return"], float) or np.isnan(result["logreg_annual_return"])


def test_ml_baseline_no_lookahead_in_features():
    src = inspect.getsource(MLBaseline._build_features)
    assert "shift(-" not in src
    assert ".shift(1)" in src
