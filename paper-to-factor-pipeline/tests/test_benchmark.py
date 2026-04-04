import numpy as np
import pandas as pd

from src.benchmark import SPYBenchmark
from src.metrics import annualized_return


def test_spy_benchmark_returns_dict(monkeypatch):
    def _mock_download(*args, **kwargs):
        idx = pd.bdate_range("2024-01-01", periods=10)
        close = pd.Series(np.linspace(100, 110, len(idx)), index=idx)
        return pd.DataFrame({"Close": close, "Open": close, "High": close, "Low": close, "Volume": 1_000_000})

    monkeypatch.setattr("src.benchmark.yf.download", _mock_download)
    result = SPYBenchmark("2024-01-01", "2024-01-20").run()

    for key in ["sharpe_ratio", "annualized_return", "max_drawdown", "returns_series"]:
        assert key in result


def test_spy_benchmark_handles_download_failure(monkeypatch):
    def _raise(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr("src.benchmark.yf.download", _raise)
    result = SPYBenchmark("2024-01-01", "2024-01-20").run()

    assert np.isnan(result["sharpe_ratio"])
    assert np.isnan(result["annualized_return"])
    assert np.isnan(result["max_drawdown"])


def test_spy_benchmark_uses_consistent_annualization(monkeypatch):
    close = pd.Series([100.0, 101.0, 102.0, 103.0], index=pd.bdate_range("2024-01-01", periods=4))

    def _mock_download(*args, **kwargs):
        return pd.DataFrame({"Close": close, "Open": close, "High": close, "Low": close, "Volume": 1_000_000})

    monkeypatch.setattr("src.benchmark.yf.download", _mock_download)
    result = SPYBenchmark("2024-01-01", "2024-01-10").run()

    expected = annualized_return(close.pct_change(fill_method=None).dropna())
    assert abs(result["annualized_return"] - expected) < 1e-12
