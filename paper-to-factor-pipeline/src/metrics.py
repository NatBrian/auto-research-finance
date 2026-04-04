import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def annualized_return(returns: pd.Series, periods_per_year: int = 252) -> float:
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
    returns = returns.dropna()
    if returns.empty:
        return np.nan
    excess = returns.mean() - (risk_free_rate / periods_per_year)
    std = returns.std(ddof=0)
    if std == 0:
        return np.nan
    return float((excess / std) * np.sqrt(periods_per_year))


def information_coefficient(signals: pd.Series, forward_returns: pd.Series) -> float:
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
    returns = returns.fillna(0.0)
    equity = (1.0 + returns).cumprod()
    peak = equity.cummax()
    drawdown = (equity / peak) - 1.0
    return float(drawdown.min())


def annualized_turnover(signals: pd.Series) -> float:
    ranked = signals.groupby(level="date").rank(pct=True)
    centered = ranked.groupby(level="date").transform(lambda x: x - x.mean())
    norm = centered.abs().groupby(level="date").transform("sum").replace(0.0, np.nan)
    weights = centered / norm

    weight_matrix = weights.unstack("ticker").sort_index()
    daily_turnover = weight_matrix.diff().abs().sum(axis=1)
    return float(daily_turnover.mean(skipna=True) * 252)
