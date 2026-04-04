import numpy as np
import pandas as pd

from src.metrics import annualized_return, information_coefficient, max_drawdown, sharpe_ratio


def test_sharpe_ratio_known_value():
    returns = pd.Series([0.01, 0.02, 0.03], dtype=float)
    expected = (returns.mean() / returns.std(ddof=0)) * np.sqrt(252)
    assert abs(sharpe_ratio(returns) - expected) < 1e-6


def test_sharpe_ratio_zero_std_returns_nan():
    returns = pd.Series([0.01, 0.01, 0.01], dtype=float)
    assert np.isnan(sharpe_ratio(returns))


def test_annualized_return_known_value():
    returns = pd.Series([0.01, -0.02, 0.03], dtype=float)
    expected = float((1.0 + returns).prod() ** (252 / len(returns)) - 1.0)
    assert abs(annualized_return(returns) - expected) < 1e-9


def test_information_coefficient_perfect_signal():
    dates = pd.to_datetime(["2024-01-01"] * 5 + ["2024-01-02"] * 5)
    tickers = ["A", "B", "C", "D", "E"] * 2
    index = pd.MultiIndex.from_arrays([dates, tickers], names=["date", "ticker"])
    signals = pd.Series([1, 2, 3, 4, 5] * 2, index=index)
    fwd = pd.Series([1, 2, 3, 4, 5] * 2, index=index)

    ic = information_coefficient(signals, fwd)
    assert abs(ic - 1.0) < 1e-9


def test_max_drawdown_known_series():
    returns = pd.Series([0.10, -0.20, 0.05, -0.10], dtype=float)
    # Equity: 1.10 -> 0.88 -> 0.924 -> 0.8316, peak=1.10, min drawdown=(0.8316/1.10)-1=-0.244
    assert abs(max_drawdown(returns) - (-0.244)) < 1e-9
