from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.prepare import DataLoader, PROJECT_ROOT
from src.utils import DataUnavailableError


def _clear_cache(start: str, end: str) -> None:
    cache = PROJECT_ROOT / f"data/cache/market_data_{start}_{end}.parquet"
    if cache.exists():
        cache.unlink()


def _mock_download(tickers, start, end, auto_adjust=True, progress=False):
    if isinstance(tickers, str):
        tickers = tickers.split()

    dates = pd.bdate_range(start=start, end=end)
    fields = ["Open", "High", "Low", "Close", "Volume"]
    data = {}

    for ticker in tickers:
        base = np.linspace(100, 120, len(dates))
        if ticker == "BBBY":
            close = np.full(len(dates), np.nan)
            real_days = min(10, len(dates))
            close[:real_days] = np.linspace(20, 16, real_days)
        else:
            close = base + np.sin(np.arange(len(dates)) / 5.0)

        open_px = close * 0.99
        high = close * 1.01
        low = close * 0.98
        volume = np.where(np.isnan(close), np.nan, 1_000_000)

        values = {
            "Open": open_px,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        }
        for field in fields:
            data[(field, ticker)] = values[field]

    return pd.DataFrame(data, index=dates)


def _max_nan_streak(series: pd.Series) -> int:
    is_nan = series.isna().to_numpy()
    max_streak = 0
    cur = 0
    for flag in is_nan:
        if flag:
            cur += 1
            max_streak = max(max_streak, cur)
        else:
            cur = 0
    return max_streak


def test_load_returns_multiindex_dataframe(monkeypatch):
    start, end = "2020-01-01", "2020-03-31"
    _clear_cache(start, end)
    monkeypatch.setattr("src.prepare.yf.download", _mock_download)

    df = DataLoader().load(start, end)

    assert isinstance(df, pd.DataFrame)
    assert list(df.index.names) == ["date", "ticker"]
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        assert col in df.columns


def test_synthetic_delisting_injected(monkeypatch):
    start, end = "2023-01-03", "2023-06-30"
    _clear_cache(start, end)
    monkeypatch.setattr("src.prepare.yf.download", _mock_download)

    df = DataLoader().load(start, end)
    bbby = df.xs("BBBY", level="ticker")

    assert "BBBY" in df.index.get_level_values("ticker")
    assert bbby.tail(5)[["Open", "High", "Low", "Close", "Volume"]].isna().all().all()


def test_removed_ticker_excluded_after_start(monkeypatch):
    start, end = "2023-06-01", "2023-07-31"
    _clear_cache(start, end)
    monkeypatch.setattr("src.prepare.yf.download", _mock_download)

    df = DataLoader().load(start, end)

    assert "BBBY" not in df.index.get_level_values("ticker")


def test_active_universe_excludes_future_and_removed_names():
    loader = DataLoader()
    loader.universe_df = pd.DataFrame(
        {
            "Ticker": ["ACTIVE", "REMOVED", "FUTURE"],
            "Date_Added": pd.to_datetime(["2010-01-01", "2010-01-01", "2020-02-01"]),
            "Date_Removed": pd.to_datetime([None, "2019-12-31", None]),
        }
    )

    active = loader._active_universe("2020-01-15")

    assert active == ["ACTIVE"]


def test_active_tickers_present(monkeypatch):
    start, end = "2020-01-01", "2021-01-01"
    _clear_cache(start, end)
    monkeypatch.setattr("src.prepare.yf.download", _mock_download)

    df = DataLoader().load(start, end)
    for ticker in ["AAPL", "MSFT"]:
        series = df.xs(ticker, level="ticker")["Close"]
        assert ticker in df.index.get_level_values("ticker")
        assert _max_nan_streak(series) <= 10


def test_data_unavailable_error(monkeypatch):
    start, end = "2022-01-01", "2022-03-01"
    _clear_cache(start, end)

    def _raise(*args, **kwargs):
        raise RuntimeError("download failed")

    monkeypatch.setattr("src.prepare.yf.download", _raise)

    with pytest.raises(DataUnavailableError):
        DataLoader().load(start, end)
