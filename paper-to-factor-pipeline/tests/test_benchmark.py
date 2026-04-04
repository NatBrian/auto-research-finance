import numpy as np
import pandas as pd

from src.benchmark import SPYBenchmark


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
