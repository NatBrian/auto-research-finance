"""Performance metrics for trading strategies."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def annualized_return(returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    Compute annualized geometric return.

    Args:
        returns: Daily return series.
        periods_per_year: Number of periods in a year (252 for daily).

    Returns:
        Annualized return as a decimal (e.g., 0.10 = 10%).
    """
    returns = returns.dropna().astype(float)
    if returns.empty:
        return np.nan

    cumulative = float((1.0 + returns).prod())
    if cumulative <= 0.0:
        return np.nan

    years = len(returns) / float(periods_per_year)
    if years <= 0:
        return np.nan

    return float(cumulative ** (1.0 / years) - 1.0)


def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """
    Compute annualized Sharpe ratio.

    Args:
        returns: Daily return series.
        risk_free_rate: Annual risk-free rate (e.g., 0.02 for 2%).
        periods_per_year: Number of periods in a year.

    Returns:
        Annualized Sharpe ratio.
    """
    returns = returns.dropna()
    if returns.empty:
        return np.nan
    excess = returns.mean() - (risk_free_rate / periods_per_year)
    std = returns.std(ddof=0)
    if std == 0:
        return np.nan
    return float((excess / std) * np.sqrt(periods_per_year))


def sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    """
    Compute annualized Sortino ratio (uses downside deviation only).

    The Sortino ratio penalizes only downside volatility, making it
    more appropriate for strategies with asymmetric return distributions.

    Args:
        returns: Daily return series.
        risk_free_rate: Annual risk-free rate.
        periods_per_year: Number of periods in a year.

    Returns:
        Annualized Sortino ratio.
    """
    returns = returns.dropna()
    if returns.empty:
        return np.nan

    excess = returns.mean() - (risk_free_rate / periods_per_year)

    # Downside deviation: std of negative returns only
    downside_returns = returns[returns < 0]
    if downside_returns.empty:
        return np.inf if excess > 0 else np.nan

    downside_std = np.sqrt((downside_returns ** 2).mean())
    if downside_std == 0:
        return np.inf if excess > 0 else np.nan

    return float((excess / downside_std) * np.sqrt(periods_per_year))


def calmar_ratio(returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    Compute Calmar ratio (annual return / max drawdown).

    The Calmar ratio measures return per unit of drawdown risk.
    Higher values indicate better risk-adjusted performance.

    Args:
        returns: Daily return series.
        periods_per_year: Number of periods in a year.

    Returns:
        Calmar ratio (positive values are better).
    """
    annual_ret = annualized_return(returns, periods_per_year)
    mdd = max_drawdown(returns)

    if np.isnan(annual_ret) or np.isnan(mdd):
        return np.nan

    if mdd == 0:
        return np.inf if annual_ret > 0 else np.nan

    # Max drawdown is negative, so we divide by absolute value
    return float(annual_ret / abs(mdd))


def information_coefficient(signals: pd.Series, forward_returns: pd.Series) -> float:
    """
    Compute information coefficient (IC) between signals and forward returns.

    IC is the mean Spearman rank correlation between signals and subsequent
    returns, computed cross-sectionally each day.

    Args:
        signals: Signal series with MultiIndex (date, ticker).
        forward_returns: Forward return series with same index.

    Returns:
        Mean daily IC value.
    """
    joined = pd.concat([signals.rename("signal"), forward_returns.rename("fwd")], axis=1)
    joined = joined.dropna()
    if joined.empty:
        return np.nan

    ic_values: list[float] = []
    for _, daily in joined.groupby(level="date"):
        if len(daily) < 5:
            continue
        if daily["signal"].nunique(dropna=True) <= 1 or daily["fwd"].nunique(dropna=True) <= 1:
            continue
        corr, _ = spearmanr(daily["signal"], daily["fwd"])
        if np.isfinite(corr):
            ic_values.append(float(corr))

    if not ic_values:
        return np.nan
    return float(np.mean(ic_values))


def max_drawdown(returns: pd.Series) -> float:
    """
    Compute maximum drawdown (peak-to-trough decline).

    Args:
        returns: Daily return series.

    Returns:
        Maximum drawdown as a negative decimal (e.g., -0.20 = 20% decline).
    """
    returns = returns.fillna(0.0)
    equity = (1.0 + returns).cumprod()
    peak = equity.cummax()
    drawdown = (equity / peak) - 1.0
    return float(drawdown.min())


def annualized_turnover(signals: pd.Series) -> float:
    """
    Compute annualized portfolio turnover.

    Turnover measures how much the portfolio changes over time.
    Higher turnover implies higher transaction costs.

    Args:
        signals: Signal series with MultiIndex (date, ticker).

    Returns:
        Annualized turnover (average daily turnover * 252).
    """
    ranked = signals.groupby(level="date").rank(pct=True)
    centered = ranked.groupby(level="date").transform(lambda x: x - x.mean())
    norm = centered.abs().groupby(level="date").transform("sum").replace(0.0, np.nan)
    weights = centered / norm

    weight_matrix = weights.unstack("ticker").sort_index()
    daily_turnover = weight_matrix.diff().abs().sum(axis=1)
    return float(daily_turnover.mean(skipna=True) * 252)


def beta_to_benchmark(
    returns: pd.Series,
    benchmark_returns: pd.Series,
) -> float:
    """
    Compute beta coefficient relative to benchmark.

    Beta measures systematic risk exposure to the benchmark.
    Beta > 1 means higher volatility than benchmark.

    Args:
        returns: Strategy return series.
        benchmark_returns: Benchmark return series (e.g., SPY).

    Returns:
        Beta coefficient.
    """
    # Align indices
    aligned = pd.concat(
        [returns.rename("strategy"), benchmark_returns.rename("benchmark")],
        axis=1,
    ).dropna()

    if aligned.empty or len(aligned) < 10:
        return np.nan

    cov = aligned["strategy"].cov(aligned["benchmark"])
    var = aligned["benchmark"].var(ddof=0)

    if var == 0:
        return np.nan

    return float(cov / var)


def rolling_sharpe(
    returns: pd.Series,
    window: int = 63,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
) -> pd.Series:
    """
    Compute rolling Sharpe ratio.

    Useful for detecting regime changes or performance degradation over time.

    Args:
        returns: Daily return series.
        window: Rolling window size in days (default: 63 = ~3 months).
        periods_per_year: Number of periods in a year.
        risk_free_rate: Annual risk-free rate.

    Returns:
        Series of rolling Sharpe ratios.
    """
    returns = returns.dropna()

    excess = returns - (risk_free_rate / periods_per_year)

    rolling_mean = excess.rolling(window=window).mean()
    rolling_std = returns.rolling(window=window).std(ddof=0)

    rolling_sharpe_values = (rolling_mean / rolling_std) * np.sqrt(periods_per_year)

    return rolling_sharpe_values


def rolling_ic(
    signals: pd.Series,
    forward_returns: pd.Series,
    window: int = 63,
) -> pd.Series:
    """
    Compute rolling information coefficient.

    Args:
        signals: Signal series with MultiIndex (date, ticker).
        forward_returns: Forward return series with same index.
        window: Rolling window size in days.

    Returns:
        Series of rolling IC values (indexed by date).
    """
    joined = pd.concat([signals.rename("signal"), forward_returns.rename("fwd")], axis=1)
    joined = joined.dropna()

    if joined.empty:
        return pd.Series(dtype=float)

    dates = joined.index.get_level_values("date").unique()
    dates = sorted(dates)

    ic_by_date = {}
    for date in dates:
        daily = joined.xs(date, level="date")
        if len(daily) < 5:
            continue
        if daily["signal"].nunique(dropna=True) <= 1 or daily["fwd"].nunique(dropna=True) <= 1:
            continue
        corr, _ = spearmanr(daily["signal"], daily["fwd"])
        if np.isfinite(corr):
            ic_by_date[date] = corr

    ic_series = pd.Series(ic_by_date)
    ic_series.name = "ic"

    return ic_series.rolling(window=window).mean()


def sector_exposure(
    weights: pd.Series,
    sector_map: dict[str, str],
) -> dict[str, float]:
    """
    Compute sector exposure from portfolio weights.

    Args:
        weights: Weight series with MultiIndex (date, ticker) or single index by ticker.
        sector_map: Dictionary mapping ticker to sector name.

    Returns:
        Dictionary mapping sector to total weight.
    """
    if isinstance(weights.index, pd.MultiIndex):
        # Take the most recent date
        latest_date = weights.index.get_level_values("date").max()
        weights = weights.xs(latest_date, level="date")

    exposure: dict[str, float] = {}
    for ticker, weight in weights.items():
        if pd.isna(weight):
            continue
        sector = sector_map.get(ticker, "Unknown")
        exposure[sector] = exposure.get(sector, 0.0) + abs(weight)

    return exposure


def hit_rate(signals: pd.Series, forward_returns: pd.Series) -> float:
    """
    Compute hit rate (percentage of correct directional predictions).

    Args:
        signals: Signal series.
        forward_returns: Forward return series.

    Returns:
        Hit rate as a decimal (e.g., 0.55 = 55% correct).
    """
    joined = pd.concat([signals.rename("signal"), forward_returns.rename("fwd")], axis=1)
    joined = joined.dropna()

    if joined.empty:
        return np.nan

    # Correct if signal and return have same sign
    correct = (joined["signal"] * joined["fwd"]) > 0

    return float(correct.mean())


def profit_factor(returns: pd.Series) -> float:
    """
    Compute profit factor (gross profits / gross losses).

    A profit factor > 1 indicates profitable strategy on average.
    Higher values indicate better risk/reward.

    Args:
        returns: Daily return series.

    Returns:
        Profit factor.
    """
    returns = returns.dropna()
    if returns.empty:
        return np.nan

    gross_profits = returns[returns > 0].sum()
    gross_losses = abs(returns[returns < 0].sum())

    if gross_losses == 0:
        return np.inf if gross_profits > 0 else np.nan

    return float(gross_profits / gross_losses)