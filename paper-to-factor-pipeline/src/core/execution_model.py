"""Execution model for applying transaction costs and position sizing."""

from __future__ import annotations

import numpy as np
import pandas as pd


def _normalize_weights(signals: pd.Series) -> pd.Series:
    """
    Normalize signals to dollar-neutral portfolio weights.

    Weights are:
    1. Ranked cross-sectionally (percentile)
    2. Centered around zero (long/short balance)
    3. Normalized so absolute weights sum to 1

    Args:
        signals: Raw signal series with MultiIndex (date, ticker).

    Returns:
        Normalized weight series.
    """
    ranked = signals.groupby(level="date").rank(pct=True)
    centered = ranked.groupby(level="date").transform(lambda x: x - x.mean())
    denom = centered.abs().groupby(level="date").transform("sum").replace(0.0, np.nan)
    return centered / denom


def apply_costs(
    signals: pd.Series,
    prices: pd.DataFrame,
    cost_bps: int = 10,
    max_leverage: float = 1.0,
) -> pd.Series:
    """
    Apply transaction costs and compute net returns.

    Args:
        signals: Signal series with MultiIndex (date, ticker).
        prices: Price DataFrame with OHLCV columns.
        cost_bps: Transaction cost in basis points (default: 10 bps).
        max_leverage: Maximum gross leverage allowed (default: 1.0).

    Returns:
        Series of net daily returns.
    """
    signals = signals.sort_index()
    prices = prices.sort_index()

    weights = _normalize_weights(signals).fillna(0.0)

    # Apply leverage cap
    gross_leverage = weights.abs().groupby(level="date").sum()
    leverage_ratio = gross_leverage / max_leverage
    leverage_ratio = leverage_ratio.replace(0.0, 1.0)
    weights = weights / leverage_ratio

    close = prices["Close"].astype(float)
    asset_returns = close.groupby(level="ticker").pct_change(fill_method=None).fillna(0.0)
    gross_returns = (weights * asset_returns).groupby(level="date").sum(min_count=1).fillna(0.0)

    # Trading costs: change in weight * cost (as fraction of portfolio)
    weight_delta = weights.groupby(level="ticker").diff().abs().fillna(0.0)
    cost_fraction = cost_bps / 10000.0  # e.g., 10 bps = 0.001
    trading_costs = (weight_delta * cost_fraction).groupby(level="date").sum(min_count=1).fillna(0.0)

    net_returns = gross_returns - trading_costs
    net_returns.name = "net_returns"
    return net_returns


def compute_positions(
    signals: pd.Series,
    capital: float = 1_000_000,
    max_position_weight: float = 0.10,
) -> pd.DataFrame:
    """
    Compute position sizes in dollars from signals.

    Args:
        signals: Signal series with MultiIndex (date, ticker).
        capital: Total capital to allocate.
        max_position_weight: Maximum weight for single position.

    Returns:
        DataFrame with position values per (date, ticker).
    """
    weights = _normalize_weights(signals)

    # Apply max position constraint
    weights = weights.clip(-max_position_weight, max_position_weight)

    # Re-normalize after clipping
    weight_sum = weights.abs().groupby(level="date").sum()
    weights = weights / weight_sum.replace(0.0, 1.0)

    positions = weights * capital
    positions.name = "position"

    return positions.reset_index().pivot(
        index="date",
        columns="ticker",
        values="position",
    )