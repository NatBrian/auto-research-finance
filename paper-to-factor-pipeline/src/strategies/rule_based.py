"""Rule-based trading strategies."""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from src.strategies.base import RuleBasedStrategy


class SimpleFactor(RuleBasedStrategy):
    """
    Wrapper for simple signal functions.

    This class wraps a standalone generate_signals function,
    providing backward compatibility with the old factor interface.

    Example:
        def momentum_signal(data):
            close = data["Close"]
            ret_12m = close.groupby(level='ticker').pct_change(252)
            return ret_12m.groupby(level='date').rank(pct=True)

        factor = SimpleFactor(momentum_signal, name="12M_Momentum")
        signals = factor.generate_signals(data)
    """

    def __init__(
        self,
        signal_fn: Callable[[pd.DataFrame], pd.Series],
        name: str = "SimpleFactor",
        description: str = "",
    ):
        """
        Initialize with a signal function.

        Args:
            signal_fn: Function that takes DataFrame and returns signal Series.
            name: Factor name for logging.
            description: Factor description.
        """
        super().__init__()
        self._signal_fn = signal_fn
        self._name = name
        self._description = description

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals using the wrapped function."""
        self.validate_data(data)
        return self._signal_fn(data)

    def __repr__(self) -> str:
        return f"SimpleFactor(name={self._name})"


class MomentumFactor(RuleBasedStrategy):
    """
    Cross-sectional momentum factor.

    Implements the classic Jegadeesh-Titman (1993) momentum strategy:
    Buy past winners, sell past losers.
    """

    def __init__(
        self,
        lookback: int = 252,
        skip: int = 21,
        normalize: bool = True,
    ):
        """
        Initialize momentum factor.

        Args:
            lookback: Lookback period in days (default: 252 = 1 year).
            skip: Days to skip before lookback (avoid short-term reversal).
            normalize: Whether to cross-sectionally rank signals.
        """
        super().__init__()
        self._lookback = lookback
        self._skip = skip
        self._normalize = normalize
        self._hyperparameters = {
            "lookback": lookback,
            "skip": skip,
            "normalize": normalize,
        }

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate momentum signals."""
        self.validate_data(data)

        close = data["Close"].astype(float)

        # Compute momentum with skip
        close_lag = close.groupby(level="ticker").shift(self._skip)
        close_lookback = close.groupby(level="ticker").shift(self._skip + self._lookback)

        momentum = close_lag / close_lookback - 1.0

        if self._normalize:
            # Cross-sectional rank
            signals = momentum.groupby(level="date").rank(pct=True)
        else:
            signals = momentum

        return signals

    def __repr__(self) -> str:
        return f"MomentumFactor(lookback={self._lookback}, skip={self._skip})"


class MeanReversionFactor(RuleBasedStrategy):
    """
    Mean reversion factor.

    Implements short-term mean reversion: Buy recent losers, sell recent winners.
    """

    def __init__(
        self,
        lookback: int = 20,
        normalize: bool = True,
    ):
        """
        Initialize mean reversion factor.

        Args:
            lookback: Lookback period in days (default: 20 = 1 month).
            normalize: Whether to cross-sectionally rank signals.
        """
        super().__init__()
        self._lookback = lookback
        self._normalize = normalize
        self._hyperparameters = {
            "lookback": lookback,
            "normalize": normalize,
        }

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate mean reversion signals (inverted recent returns)."""
        self.validate_data(data)

        close = data["Close"].astype(float)

        # Compute recent returns
        close_lag1 = close.groupby(level="ticker").shift(1)
        close_lookback = close.groupby(level="ticker").shift(self._lookback)

        recent_ret = close_lag1 / close_lookback - 1.0

        # Invert for mean reversion (buy losers, sell winners)
        signals = -recent_ret

        if self._normalize:
            signals = signals.groupby(level="date").rank(pct=True)

        return signals

    def __repr__(self) -> str:
        return f"MeanReversionFactor(lookback={self._lookback})"


class VolatilityFactor(RuleBasedStrategy):
    """
    Low volatility factor.

    Implements the low volatility anomaly: Low vol stocks tend to outperform.
    """

    def __init__(
        self,
        lookback: int = 60,
        normalize: bool = True,
    ):
        """
        Initialize volatility factor.

        Args:
            lookback: Lookback period for volatility calculation.
            normalize: Whether to cross-sectionally rank signals.
        """
        super().__init__()
        self._lookback = lookback
        self._normalize = normalize
        self._hyperparameters = {
            "lookback": lookback,
            "normalize": normalize,
        }

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate low volatility signals (prefer low vol)."""
        self.validate_data(data)

        close = data["Close"].astype(float)

        # Compute daily returns
        ret = close.groupby(level="ticker").pct_change()

        # Rolling volatility
        vol = ret.groupby(level="ticker").transform(
            lambda x: x.rolling(self._lookback).std()
        )

        # Shift to avoid look-ahead
        vol = vol.groupby(level="ticker").shift(1)

        # Invert (prefer low volatility)
        signals = -vol

        if self._normalize:
            signals = signals.groupby(level="date").rank(pct=True)

        return signals

    def __repr__(self) -> str:
        return f"VolatilityFactor(lookback={self._lookback})"


class RSIFactor(RuleBasedStrategy):
    """
    RSI-based factor.

    Uses RSI extremes to generate contrarian signals.
    """

    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        normalize: bool = True,
    ):
        """
        Initialize RSI factor.

        Args:
            period: RSI calculation period.
            oversold: RSI level considered oversold.
            overbought: RSI level considered overbought.
            normalize: Whether to cross-sectionally rank signals.
        """
        super().__init__()
        self._period = period
        self._oversold = oversold
        self._overbought = overbought
        self._normalize = normalize
        self._hyperparameters = {
            "period": period,
            "oversold": oversold,
            "overbought": overbought,
        }

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate RSI-based signals."""
        self.validate_data(data)

        close = data["Close"].astype(float)
        delta = close.groupby(level="ticker").diff()

        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.groupby(level="ticker").transform(
            lambda x: x.rolling(self._period).mean()
        )
        avg_loss = loss.groupby(level="ticker").transform(
            lambda x: x.rolling(self._period).mean()
        )

        rs = avg_gain / avg_loss.replace(0.0, np.nan)
        rsi = 100.0 - (100.0 / (1.0 + rs))

        # Shift to avoid look-ahead
        rsi = rsi.groupby(level="ticker").shift(1)

        # Contrarian signal: buy oversold, sell overbought
        # Center around 50
        signals = 50.0 - rsi

        if self._normalize:
            signals = signals.groupby(level="date").rank(pct=True)

        return signals

    def __repr__(self) -> str:
        return f"RSIFactor(period={self._period})"