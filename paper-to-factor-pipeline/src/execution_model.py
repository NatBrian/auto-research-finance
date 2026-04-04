import numpy as np
import pandas as pd


def _normalize_weights(signals: pd.Series) -> pd.Series:
    ranked = signals.groupby(level="date").rank(pct=True)
    centered = ranked.groupby(level="date").transform(lambda x: x - x.mean())
    denom = centered.abs().groupby(level="date").transform("sum").replace(0.0, np.nan)
    return centered / denom


def apply_costs(signals: pd.Series, prices: pd.DataFrame, cost_bps: int = 10) -> pd.Series:
    signals = signals.sort_index()
    prices = prices.sort_index()

    weights = _normalize_weights(signals).fillna(0.0)

    close = prices["Close"].astype(float)
    asset_returns = close.groupby(level="ticker").pct_change(fill_method=None).fillna(0.0)
    gross_returns = (weights * asset_returns).groupby(level="date").sum(min_count=1).fillna(0.0)

    signal_delta = signals.groupby(level="ticker").diff().abs().fillna(0.0)
    cost_per_unit = (cost_bps / 10000.0) * close
    trading_costs = (signal_delta * cost_per_unit).groupby(level="date").sum(min_count=1).fillna(0.0)

    net_returns = gross_returns - trading_costs
    net_returns.name = "net_returns"
    return net_returns
