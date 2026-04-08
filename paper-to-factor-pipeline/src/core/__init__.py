"""Core infrastructure for paper-to-factor pipeline."""

from src.core.base import BaseStrategy, StrategyType
from src.core.metrics import (
    annualized_return,
    annualized_turnover,
    information_coefficient,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
    beta_to_benchmark,
    rolling_sharpe,
)
from src.core.execution_model import apply_costs

__all__ = [
    "BaseStrategy",
    "StrategyType",
    "annualized_return",
    "annualized_turnover",
    "information_coefficient",
    "max_drawdown",
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "beta_to_benchmark",
    "rolling_sharpe",
    "apply_costs",
]