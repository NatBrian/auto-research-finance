import numpy as np
import pandas as pd
import yfinance as yf

from src.metrics import max_drawdown, sharpe_ratio
from src.utils import setup_logging


class SPYBenchmark:
    def __init__(self, start_date: str, end_date: str):
        self.start_date = start_date
        self.end_date = end_date
        self.logger = setup_logging()

    def run(self) -> dict:
        try:
            data = yf.download(
                "SPY",
                start=self.start_date,
                end=self.end_date,
                auto_adjust=True,
                progress=False,
            )
            close = data["Close"].dropna().astype(float)
            if close.empty:
                raise ValueError("No SPY data returned")

            returns = np.log(close / close.shift(1)).dropna()
            annual_return = float(returns.mean() * 252)
            return {
                "sharpe_ratio": sharpe_ratio(returns),
                "annualized_return": annual_return,
                "max_drawdown": max_drawdown(returns),
                "returns_series": returns,
            }
        except Exception as exc:
            self.logger.warning("SPY benchmark download failed: %s", exc)
            return {
                "sharpe_ratio": np.nan,
                "annualized_return": np.nan,
                "max_drawdown": np.nan,
                "returns_series": pd.Series(dtype=float),
            }
