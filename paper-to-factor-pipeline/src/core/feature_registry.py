"""Feature registry for extensible feature engineering."""

from __future__ import annotations

import logging
from typing import Callable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# Type alias for feature functions
FeatureFunction = Callable[[pd.DataFrame], pd.Series]


class FeatureRegistry:
    """
    Registry for feature engineering functions.

    Features are registered by name and can be dynamically selected
    for ML model training.
    """

    _features: dict[str, FeatureFunction] = {}
    _feature_categories: dict[str, str] = {}

    @classmethod
    def register(
        cls,
        name: str,
        category: str = "custom",
    ) -> Callable[[FeatureFunction], FeatureFunction]:
        """
        Decorator to register a feature function.

        Args:
            name: Feature name.
            category: Feature category (momentum, volatility, volume, etc.).

        Returns:
            Decorator function.

        Example:
            @FeatureRegistry.register("ret_5d", category="momentum")
            def ret_5d(data: pd.DataFrame) -> pd.Series:
                ...
        """
        def decorator(func: FeatureFunction) -> FeatureFunction:
            cls._features[name] = func
            cls._feature_categories[name] = category
            return func
        return decorator

    @classmethod
    def get(cls, name: str) -> FeatureFunction:
        """Get a feature function by name."""
        if name not in cls._features:
            raise KeyError(f"Feature '{name}' not registered. Available: {list(cls._features.keys())}")
        return cls._features[name]

    @classmethod
    def list_features(cls) -> list[str]:
        """List all registered feature names."""
        return sorted(cls._features.keys())

    @classmethod
    def list_by_category(cls) -> dict[str, list[str]]:
        """List features grouped by category."""
        categories: dict[str, list[str]] = {}
        for name, cat in cls._feature_categories.items():
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(name)
        return {k: sorted(v) for k, v in categories.items()}

    @classmethod
    def build_features(
        cls,
        data: pd.DataFrame,
        feature_names: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Build feature matrix from registered features.

        Args:
            data: OHLCV data with MultiIndex (date, ticker).
            feature_names: List of features to build. If None, builds all.

        Returns:
            DataFrame with engineered features.
        """
        if feature_names is None:
            feature_names = cls.list_features()

        features = {}
        for name in feature_names:
            try:
                features[name] = cls._features[name](data)
            except Exception as e:
                # Log warning but continue
                logger.warning(f"Failed to compute feature '{name}': {e}")

        return pd.DataFrame(features)


# ============================================================================
# Register default features
# ============================================================================

@FeatureRegistry.register("ret_1d", category="momentum")
def ret_1d(data: pd.DataFrame) -> pd.Series:
    """1-day log return."""
    close = data["Close"].astype(float)
    close_lag1 = close.groupby(level="ticker").shift(1)
    return np.log(close / close_lag1)


@FeatureRegistry.register("ret_5d", category="momentum")
def ret_5d(data: pd.DataFrame) -> pd.Series:
    """5-day log return."""
    close = data["Close"].astype(float)
    close_lag1 = close.groupby(level="ticker").shift(1)
    close_lag5 = close.groupby(level="ticker").shift(6)
    return np.log(close_lag1 / close_lag5)


@FeatureRegistry.register("ret_20d", category="momentum")
def ret_20d(data: pd.DataFrame) -> pd.Series:
    """20-day log return."""
    close = data["Close"].astype(float)
    close_lag1 = close.groupby(level="ticker").shift(1)
    close_lag20 = close.groupby(level="ticker").shift(21)
    return np.log(close_lag1 / close_lag20)


@FeatureRegistry.register("ret_60d", category="momentum")
def ret_60d(data: pd.DataFrame) -> pd.Series:
    """60-day (3-month) log return."""
    close = data["Close"].astype(float)
    close_lag1 = close.groupby(level="ticker").shift(1)
    close_lag60 = close.groupby(level="ticker").shift(61)
    return np.log(close_lag1 / close_lag60)


@FeatureRegistry.register("ret_252d", category="momentum")
def ret_252d(data: pd.DataFrame) -> pd.Series:
    """252-day (1-year) log return."""
    close = data["Close"].astype(float)
    close_lag1 = close.groupby(level="ticker").shift(1)
    close_lag252 = close.groupby(level="ticker").shift(253)
    return np.log(close_lag1 / close_lag252)


@FeatureRegistry.register("momentum_12_1", category="momentum")
def momentum_12_1(data: pd.DataFrame) -> pd.Series:
    """12-1 momentum (skip most recent month)."""
    close = data["Close"].astype(float)
    close_lag1 = close.groupby(level="ticker").shift(1)
    close_lag21 = close.groupby(level="ticker").shift(21)
    close_lag252 = close.groupby(level="ticker").shift(252)
    return np.log(close_lag21 / close_lag252)


@FeatureRegistry.register("volatility_5d", category="volatility")
def volatility_5d(data: pd.DataFrame) -> pd.Series:
    """5-day rolling volatility."""
    close = data["Close"].astype(float)
    ret = np.log(close / close.groupby(level="ticker").shift(1))
    vol = ret.groupby(level="ticker").transform(lambda x: x.rolling(5).std())
    return vol.groupby(level="ticker").shift(1)


@FeatureRegistry.register("volatility_20d", category="volatility")
def volatility_20d(data: pd.DataFrame) -> pd.Series:
    """20-day rolling volatility."""
    close = data["Close"].astype(float)
    ret = np.log(close / close.groupby(level="ticker").shift(1))
    vol = ret.groupby(level="ticker").transform(lambda x: x.rolling(20).std())
    return vol.groupby(level="ticker").shift(1)


@FeatureRegistry.register("volatility_60d", category="volatility")
def volatility_60d(data: pd.DataFrame) -> pd.Series:
    """60-day rolling volatility."""
    close = data["Close"].astype(float)
    ret = np.log(close / close.groupby(level="ticker").shift(1))
    vol = ret.groupby(level="ticker").transform(lambda x: x.rolling(60).std())
    return vol.groupby(level="ticker").shift(1)


@FeatureRegistry.register("vol_ratio_20_5", category="volatility")
def vol_ratio_20_5(data: pd.DataFrame) -> pd.Series:
    """Ratio of 20d to 5d volatility (vol regime indicator)."""
    vol_20 = FeatureRegistry.get("volatility_20d")(data)
    vol_5 = FeatureRegistry.get("volatility_5d")(data)
    return vol_20 / vol_5.replace(0.0, np.nan)


@FeatureRegistry.register("vol_z_5d", category="volume")
def vol_z_5d(data: pd.DataFrame) -> pd.Series:
    """Volume z-score vs 5-day rolling mean/std."""
    volume = data["Volume"].astype(float)
    vol_lag1 = volume.groupby(level="ticker").shift(1)
    vol_mean5 = vol_lag1.groupby(level="ticker").transform(lambda x: x.rolling(5).mean())
    vol_std5 = vol_lag1.groupby(level="ticker").transform(lambda x: x.rolling(5).std())
    return (vol_lag1 - vol_mean5) / vol_std5.replace(0.0, np.nan)


@FeatureRegistry.register("vol_z_20d", category="volume")
def vol_z_20d(data: pd.DataFrame) -> pd.Series:
    """Volume z-score vs 20-day rolling mean/std."""
    volume = data["Volume"].astype(float)
    vol_lag1 = volume.groupby(level="ticker").shift(1)
    vol_mean20 = vol_lag1.groupby(level="ticker").transform(lambda x: x.rolling(20).mean())
    vol_std20 = vol_lag1.groupby(level="ticker").transform(lambda x: x.rolling(20).std())
    return (vol_lag1 - vol_mean20) / vol_std20.replace(0.0, np.nan)


@FeatureRegistry.register("volume_ratio", category="volume")
def volume_ratio(data: pd.DataFrame) -> pd.Series:
    """Ratio of current volume to 20-day average."""
    volume = data["Volume"].astype(float)
    vol_lag1 = volume.groupby(level="ticker").shift(1)
    vol_mean20 = vol_lag1.groupby(level="ticker").transform(lambda x: x.rolling(20).mean())
    return vol_lag1 / vol_mean20.replace(0.0, np.nan)


@FeatureRegistry.register("rsi_14d", category="technical")
def rsi_14d(data: pd.DataFrame) -> pd.Series:
    """14-day Relative Strength Index."""
    close = data["Close"].astype(float)
    delta = close.groupby(level="ticker").diff()

    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.groupby(level="ticker").transform(lambda x: x.rolling(14).mean())
    avg_loss = loss.groupby(level="ticker").transform(lambda x: x.rolling(14).mean())

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))

    return rsi.groupby(level="ticker").shift(1)


@FeatureRegistry.register("bb_position", category="technical")
def bb_position(data: pd.DataFrame) -> pd.Series:
    """Bollinger Band position (0-1, >1 above upper, <0 below lower)."""
    close = data["Close"].astype(float)
    close_lag1 = close.groupby(level="ticker").shift(1)

    sma_20 = close_lag1.groupby(level="ticker").transform(lambda x: x.rolling(20).mean())
    std_20 = close_lag1.groupby(level="ticker").transform(lambda x: x.rolling(20).std())

    upper = sma_20 + 2 * std_20
    lower = sma_20 - 2 * std_20

    return (close_lag1 - lower) / (upper - lower).replace(0.0, np.nan)


@FeatureRegistry.register("atr_ratio", category="technical")
def atr_ratio(data: pd.DataFrame) -> pd.Series:
    """Average True Range as percentage of price."""
    high = data["High"].astype(float)
    low = data["Low"].astype(float)
    close = data["Close"].astype(float)
    close_prev = close.groupby(level="ticker").shift(1)

    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.groupby(level="ticker").transform(lambda x: x.rolling(14).mean())

    return atr / close.groupby(level="ticker").shift(1).replace(0.0, np.nan)


@FeatureRegistry.register("gap", category="technical")
def gap(data: pd.DataFrame) -> pd.Series:
    """Overnight gap as percentage."""
    open_px = data["Open"].astype(float)
    close = data["Close"].astype(float)
    close_prev = close.groupby(level="ticker").shift(1)

    return (open_px - close_prev) / close_prev.replace(0.0, np.nan)


@FeatureRegistry.register("intraday_range", category="technical")
def intraday_range(data: pd.DataFrame) -> pd.Series:
    """Intraday range as percentage of close."""
    high = data["High"].astype(float)
    low = data["Low"].astype(float)
    close = data["Close"].astype(float)

    return (high - low) / close.replace(0.0, np.nan)


@FeatureRegistry.register("close_to_open", category="technical")
def close_to_open(data: pd.DataFrame) -> pd.Series:
    """Close to open ratio (overnight gap from previous close to today's open)."""
    open_px = data["Open"].astype(float)
    close = data["Close"].astype(float)
    close_prev = close.groupby(level="ticker").shift(1)

    return open_px / close_prev.replace(0.0, np.nan)


@FeatureRegistry.register("adv_20d", category="volume")
def adv_20d(data: pd.DataFrame) -> pd.Series:
    """Average dollar volume over 20 days."""
    close = data["Close"].astype(float)
    volume = data["Volume"].astype(float)

    dv = close * volume
    adv = dv.groupby(level="ticker").transform(lambda x: x.rolling(20).mean())

    return adv.groupby(level="ticker").shift(1)


# Default feature set (matches original ML baseline)
DEFAULT_FEATURES = ["ret_5d", "ret_20d", "vol_z_5d", "volatility_20d"]

# Extended feature set for more sophisticated models
EXTENDED_FEATURES = [
    "ret_1d", "ret_5d", "ret_20d", "ret_60d",
    "momentum_12_1",
    "volatility_5d", "volatility_20d", "volatility_60d", "vol_ratio_20_5",
    "vol_z_5d", "vol_z_20d", "volume_ratio",
    "rsi_14d", "bb_position", "atr_ratio",
    "gap", "intraday_range",
    "adv_20d",
]