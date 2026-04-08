from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

# Install SSL patch BEFORE importing yfinance
from src.utils import DataUnavailableError, get_ssl_verify, install_ssl_patch, load_config

install_ssl_patch()

try:
    import yfinance as yf
except Exception:  # pragma: no cover - optional dependency during thin test envs
    yf = None

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover
    requests = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
logger = logging.getLogger("paper_to_factor")


class DataLoader:
    REQUIRED_COLS = ["Open", "High", "Low", "Close", "Volume"]

    def __init__(self):
        self.config = load_config()
        self.data_cfg = self.config.get("data", {})
        self.universe_path = Path(self.data_cfg.get("universe_file", "data/universe_sp500_historical.csv"))
        self.min_coverage = float(self.data_cfg.get("min_coverage_ratio", 0.30))
        self.universe_df = pd.read_csv(self.universe_path)
        self.universe_df["Date_Added"] = pd.to_datetime(self.universe_df["Date_Added"], errors="coerce")
        self.universe_df["Date_Removed"] = pd.to_datetime(self.universe_df["Date_Removed"], errors="coerce")

    def _create_session(self):
        """Create requests session with SSL settings from config."""
        if requests is None:
            return None

        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _active_universe(self, start_date: str) -> list[str]:
        start_ts = pd.Timestamp(start_date)
        active = self.universe_df[
            (self.universe_df["Date_Added"] <= start_ts)
            & (
                self.universe_df["Date_Removed"].isna()
                | (self.universe_df["Date_Removed"] > start_ts)
            )
        ]
        return sorted(active["Ticker"].dropna().astype(str).unique().tolist())

    def _removed_date_for_ticker(self, ticker: str) -> pd.Timestamp | None:
        removed = self.universe_df.loc[
            self.universe_df["Ticker"].astype(str) == str(ticker), "Date_Removed"
        ]
        if removed.empty:
            return None
        removed_ts = removed.iloc[0]
        return pd.Timestamp(removed_ts) if pd.notna(removed_ts) else None

    def _extract_ticker_frame(self, raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame(columns=self.REQUIRED_COLS)

        if isinstance(raw.columns, pd.MultiIndex):
            level0 = raw.columns.get_level_values(0)
            level1 = raw.columns.get_level_values(1)
            if ticker in level1:
                frame = raw.xs(ticker, axis=1, level=1, drop_level=True).copy()
            elif ticker in level0:
                frame = raw.xs(ticker, axis=1, level=0, drop_level=True).copy()
            else:
                frame = pd.DataFrame(index=raw.index, columns=self.REQUIRED_COLS)
        else:
            frame = raw.copy()

        frame.index = pd.to_datetime(frame.index)
        frame = frame.sort_index()

        for col in self.REQUIRED_COLS:
            if col not in frame.columns:
                frame[col] = np.nan

        return frame[self.REQUIRED_COLS]

    def _build_synthetic_zero_data(
        self,
        ticker: str,
        date_index: pd.DatetimeIndex,
        removed_date: pd.Timestamp | None = None,
    ) -> pd.DataFrame:
        n = len(date_index)
        if n == 0:
            return pd.DataFrame(columns=self.REQUIRED_COLS, index=date_index)

        seed = abs(hash((ticker, str(date_index[0]), str(date_index[-1])))) % (2**32)
        rng = np.random.default_rng(seed)

        if removed_date is not None and removed_date <= date_index[-1]:
            active_days = int((date_index <= removed_date).sum())
            if active_days <= 0:
                return pd.DataFrame(index=date_index, columns=self.REQUIRED_COLS, dtype=float)
        else:
            min_days = min(30, n)
            active_days = int(rng.integers(min_days, n + 1))

        start_price = float(rng.uniform(10.0, 50.0))

        daily_rets = rng.normal(0.0, 0.015, active_days)
        close = start_price * np.cumprod(1.0 + daily_rets)

        open_px = close * (1.0 + rng.normal(0.0, 0.002, active_days))
        high = np.maximum(open_px, close) * (1.0 + np.abs(rng.normal(0.0, 0.003, active_days)))
        low = np.minimum(open_px, close) * (1.0 - np.abs(rng.normal(0.0, 0.003, active_days)))
        volume = rng.integers(100_000, 5_000_000, active_days).astype(float)

        synthetic = pd.DataFrame(index=date_index, columns=self.REQUIRED_COLS, dtype=float)
        synthetic.iloc[:active_days] = np.column_stack([open_px, high, low, close, volume])
        logger.info(
            "Injected synthetic delisting tail for %s from %s",
            ticker,
            date_index[active_days - 1].date(),
        )
        return synthetic

    def _inject_partial_delisting(
        self,
        ticker: str,
        ticker_df: pd.DataFrame,
        date_index: pd.DatetimeIndex,
    ) -> pd.DataFrame:
        full = ticker_df.reindex(date_index)
        last_real_date = full["Close"].dropna().index.max()
        if pd.notna(last_real_date):
            full.loc[full.index > last_real_date, self.REQUIRED_COLS] = np.nan
            logger.info(
                "Injected synthetic delisting tail for %s from %s",
                ticker,
                pd.Timestamp(last_real_date).date(),
            )
        return full

    def load(self, start_date: str, end_date: str) -> pd.DataFrame:
        cache_path = PROJECT_ROOT / f"data/cache/market_data_{start_date}_{end_date}.parquet"
        if cache_path.exists():
            return pd.read_parquet(cache_path)

        universe = self._active_universe(start_date)
        if not universe:
            raise DataUnavailableError("Universe is empty for the requested date range")

        if yf is None:
            raise DataUnavailableError("yfinance is not installed")

        try:
            raw = yf.download(
                tickers=universe,
                start=start_date,
                end=end_date,
                auto_adjust=True,
                progress=False,
            )
        except Exception as exc:
            raise DataUnavailableError(f"Failed to download market data: {exc}") from exc

        date_index = pd.bdate_range(start=start_date, end=end_date)
        if date_index.empty:
            raise DataUnavailableError("No business dates available in requested range")

        ticker_frames: dict[str, pd.DataFrame] = {}
        expected_len = len(date_index)

        for ticker in universe:
            ticker_df = self._extract_ticker_frame(raw, ticker)
            close_count = int(ticker_df["Close"].dropna().shape[0]) if "Close" in ticker_df else 0

            if close_count == 0:
                ticker_frames[ticker] = self._build_synthetic_zero_data(
                    ticker,
                    date_index,
                    removed_date=self._removed_date_for_ticker(ticker),
                )
                continue

            coverage = close_count / expected_len
            if coverage < self.min_coverage:
                ticker_frames[ticker] = self._inject_partial_delisting(ticker, ticker_df, date_index)
            else:
                ticker_frames[ticker] = ticker_df.reindex(date_index)[self.REQUIRED_COLS]

        tuples: list[tuple[pd.Timestamp, str]] = []
        rows: list[list[float]] = []
        for ticker, frame in ticker_frames.items():
            for dt, row in frame.iterrows():
                tuples.append((pd.Timestamp(dt), ticker))
                rows.append([row[c] for c in self.REQUIRED_COLS])

        df = pd.DataFrame(
            rows,
            index=pd.MultiIndex.from_tuples(tuples, names=["date", "ticker"]),
            columns=self.REQUIRED_COLS,
        ).sort_index()

        df = df.groupby(level="ticker", group_keys=False).apply(lambda x: x.ffill(limit=5))

        cache_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(cache_path)

        return df
