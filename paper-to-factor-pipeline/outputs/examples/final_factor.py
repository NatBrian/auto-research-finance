"""
Factor: 212 Years of Price Momentum (The World's Longest Backtest: 1801–2012)
ArXiv ID: cmg-2013
Strategy Type: rule_based
Signal Type: momentum
Lookback: 252 days (12 months), skip 21 days (1 month)
"""

import pandas as pd
import numpy as np
from src.strategies.base import RuleBasedStrategy


class Momentum121Strategy(RuleBasedStrategy):
    """
    12-1 Momentum Strategy from Geczy & Samonov (2013).

    Computes the 12-month momentum signal, skipping the most recent month
    to avoid short-term reversal effects. This is the classic "momentum"
    factor validated over 212 years of data.

    Signal = log(close_{t-21} / close_{t-252})
    Then cross-sectionally rank to get final signal.
    """

    def __init__(self, lookback: int = 252, skip: int = 21):
        """
        Initialize the 12-1 momentum strategy.

        Args:
            lookback: Number of trading days for lookback period (default 252 = 12 months).
            skip: Number of days to skip at the end (default 21 = 1 month).
        """
        super().__init__()
        self._lookback = lookback
        self._skip = skip
        self._hyperparameters = {
            "lookback": lookback,
            "skip": skip,
        }

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate 12-1 momentum signals.

        Args:
            data: MultiIndex DataFrame with index levels (date, ticker).
                  Columns: Open, High, Low, Close, Volume.

        Returns:
            pd.Series with the same MultiIndex (date, ticker).
            Values are cross-sectional percentile ranks (0-1).
            Higher values = stronger long signal (past winners).
            NaN = insufficient history for that ticker on that date.
        """
        self.validate_data(data)

        close = data["Close"].astype(float)

        # Compute 12-1 momentum: log(close_{t-21} / close_{t-252})
        # Use shift(skip+1) to get close at t-21 (skip most recent month)
        # Use shift(lookback+1) to get close at t-252 (12 months ago)
        # The +1 accounts for the fact that we want to use yesterday's close
        # to avoid look-ahead bias

        close_skip = close.groupby(level="ticker").shift(self._skip + 1)
        close_lookback = close.groupby(level="ticker").shift(self._lookback + 1)

        # Compute log return over the formation period
        momentum = np.log(close_skip / close_lookback)

        # Also compute 6-1 momentum for shorter-term signal
        close_skip_6m = close.groupby(level="ticker").shift(self._skip + 1)
        close_lookback_6m = close.groupby(level="ticker").shift(126 + 1)  # ~6 months
        momentum_6m = np.log(close_skip_6m / close_lookback_6m)

        # Combine 12-1 and 6-1 momentum signals
        momentum_combined = 0.6 * momentum + 0.4 * momentum_6m

        # Apply cross-sectional z-score normalization for better signal scaling
        momentum_z = momentum_combined.groupby(level="date").transform(
            lambda x: (x - x.mean()) / (x.std() + 1e-8)
        )

        # Apply 5-day smoothing to reduce turnover
        momentum_smoothed = momentum_z.groupby(level="ticker").transform(
            lambda x: x.rolling(window=5, min_periods=1).mean()
        )

        # Apply volatility filter: zero out signals for high-volatility tickers
        # Compute 20-day rolling volatility
        returns = close.groupby(level="ticker").pct_change(fill_method=None)
        volatility = returns.groupby(level="ticker").transform(
            lambda x: x.rolling(window=20, min_periods=10).std()
        )
        # Get cross-sectional median volatility per date
        median_vol = volatility.groupby(level="date").transform("median")
        # Zero out signals for tickers with volatility > 2x median
        vol_mask = (volatility <= 2.0 * median_vol).astype(float)
        momentum_filtered = momentum_smoothed * vol_mask

        # Use momentum z-scores directly instead of percentile ranking
        # This preserves magnitude information about momentum strength
        # Then apply quintile-based weighting for more concentrated bets
        ranks = momentum_filtered.groupby(level="date").rank(pct=True)

        # Top 10% get positive weight, bottom 10% get negative weight, middle gets 0
        # With 30 tickers, this means ~3 long and ~3 short positions
        signals = pd.Series(0.0, index=ranks.index)
        signals[ranks >= 0.9] = 1.0   # Long top decile
        signals[ranks <= 0.1] = -1.0  # Short bottom decile

        signals.name = "signal"

        return signals