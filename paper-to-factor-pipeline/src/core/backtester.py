"""Enhanced backtester supporting hybrid strategy architecture."""

from __future__ import annotations

import importlib
import sys
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.core.base import BaseStrategy, StrategyType
from src.core.execution_model import apply_costs
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
    hit_rate,
    profit_factor,
)
from src.core.sector_data import SectorMapper, default_mapper
from src.prepare import DataLoader
from src.validator import validate_factor
from src.utils import load_config


class EnhancedBacktester:
    """
    Enhanced backtester supporting both rule-based and ML strategies.

    Features:
    - Supports BaseStrategy interface
    - Uses validation set for early stopping
    - Computes comprehensive metrics
    - Tracks sector exposure
    - Reports feature importance
    """

    def __init__(self, config: dict):
        self.config = config
        self._sector_mapper = SectorMapper()

    def _base_result(self, status: str, message: str) -> dict[str, Any]:
        """Create base result dictionary with all metrics."""
        return {
            "status": status,
            "message": message,
            # Strategy metrics
            "sharpe_ratio": np.nan,
            "sortino_ratio": np.nan,
            "calmar_ratio": np.nan,
            "information_coefficient": np.nan,
            "ic_1d": np.nan,
            "ic_5d": np.nan,
            "ic_21d": np.nan,
            "ic_63d": np.nan,
            "annualized_return": np.nan,
            "max_drawdown": np.nan,
            "daily_turnover": np.nan,
            "hit_rate": np.nan,
            "profit_factor": np.nan,
            # Benchmark metrics
            "alpha_vs_spy": np.nan,
            "beta_to_spy": np.nan,
            "spy_sharpe": np.nan,
            "spy_annual_return": np.nan,
            # ML baseline metrics
            "xgb_sharpe": np.nan,
            "logreg_sharpe": np.nan,
            # Strategy metadata
            "strategy_type": "unknown",
            "is_fitted": False,
            "hyperparameters": {},
            "feature_names": [],
            "feature_importance": {},
            # Data info
            "universe_size": 0,
            "delisted_count": 0,
            "train_start": "",
            "train_end": "",
            "val_start": "",
            "val_end": "",
            "test_start": "",
            "test_end": "",
            # Sector exposure
            "sector_exposure": {},
            "top_sector": None,
            "sector_concentration": np.nan,
        }

    def _slice_by_dates(self, data: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
        """Slice data by date range."""
        if len(dates) == 0:
            return data.iloc[0:0].copy()
        idx = pd.IndexSlice
        return data.loc[idx[dates, :], :].copy()

    def _load_strategy(self, factor_path: str) -> BaseStrategy:
        """
        Load strategy from factor file.

        Supports both:
        1. New BaseStrategy subclasses
        2. Legacy generate_signals functions
        """
        validation = validate_factor(factor_path)
        if not validation.get("valid", False):
            raise ValueError(validation.get("issues", ["Validation failed"]))

        # Try to import as module
        sys.modules.pop("sandbox.factor", None)
        sys.modules.pop("sandbox", None)

        factor_module = importlib.import_module("sandbox.factor")

        # Check if it's a BaseStrategy subclass
        for name in dir(factor_module):
            obj = getattr(factor_module, name)
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseStrategy)
                and obj is not BaseStrategy
            ):
                return obj()

        # Fall back to legacy function wrapper
        if hasattr(factor_module, "generate_signals"):
            from src.strategies.rule_based import SimpleFactor

            return SimpleFactor(
                factor_module.generate_signals,
                name="LegacyFactor",
                description="Wrapped legacy generate_signals function",
            )

        raise ValueError("No valid strategy found in factor module")

    def _run_ml_baseline(
        self,
        train_data: pd.DataFrame,
        test_data: pd.DataFrame,
    ) -> dict[str, float]:
        """Run ML baseline comparison."""
        from src.strategies.ml_strategy import TreeBasedStrategy, LogisticRegressionStrategy

        result = {
            "xgb_sharpe": np.nan,
            "logreg_sharpe": np.nan,
        }

        try:
            # XGBoost baseline
            xgb = TreeBasedStrategy(
                model_type="xgboost",
                features=["ret_5d", "ret_20d", "vol_z_5d", "volatility_20d"],
                target_horizon=5,
            )
            xgb.fit(train_data)
            xgb_signals = xgb.generate_signals(test_data)
            xgb_returns = apply_costs(xgb_signals, test_data, cost_bps=10)
            result["xgb_sharpe"] = sharpe_ratio(xgb_returns)
        except Exception:
            pass

        try:
            # Logistic regression baseline
            lr = LogisticRegressionStrategy(
                features=["ret_5d", "ret_20d", "vol_z_5d", "volatility_20d"],
                target_horizon=5,
            )
            lr.fit(train_data)
            lr_signals = lr.generate_signals(test_data)
            lr_returns = apply_costs(lr_signals, test_data, cost_bps=10)
            result["logreg_sharpe"] = sharpe_ratio(lr_returns)
        except Exception:
            pass

        return result

    def _run_spy_benchmark(
        self,
        test_start: str,
        test_end: str,
    ) -> dict[str, float]:
        """Run SPY benchmark."""
        from src.benchmark import SPYBenchmark

        try:
            bench = SPYBenchmark(test_start, test_end).run()
            return {
                "spy_sharpe": float(bench.get("sharpe_ratio", np.nan)),
                "spy_annual_return": float(bench.get("annualized_return", np.nan)),
                "spy_returns": bench.get("returns_series", pd.Series(dtype=float)),
            }
        except Exception:
            return {
                "spy_sharpe": np.nan,
                "spy_annual_return": np.nan,
                "spy_returns": pd.Series(dtype=float),
            }

    def run(
        self,
        strategy: BaseStrategy | None = None,
        factor_path: str | None = None,
    ) -> dict[str, Any]:
        """
        Run backtest.

        Args:
            strategy: Pre-loaded strategy instance.
            factor_path: Path to factor file (if strategy not provided).

        Returns:
            Dictionary with all backtest metrics.
        """
        try:
            data_cfg = self.config.get("data", {})
            start_date = data_cfg.get("start_date", "2015-01-01")
            end_date = data_cfg.get("end_date", "2023-12-31")

            # Load data
            loader = DataLoader()
            try:
                data = loader.load(start_date, end_date)
            except Exception:
                return self._base_result("error", traceback.format_exc())

            # Load or use provided strategy
            if strategy is None:
                workflow_cfg = self.config.get("workflow", {})
                factor_path = factor_path or workflow_cfg.get("factor_path", "sandbox/factor.py")
                try:
                    strategy = self._load_strategy(factor_path)
                except Exception:
                    return self._base_result("error", traceback.format_exc())

            # Get dates
            dates = pd.DatetimeIndex(sorted(data.index.get_level_values("date").unique()))
            if len(dates) < 30:
                return self._base_result("error", "Not enough dates for train/val/test split")

            # Split data
            train_ratio = float(data_cfg.get("train_ratio", 0.60))
            valid_ratio = float(data_cfg.get("validation_ratio", 0.20))

            train_end = int(len(dates) * train_ratio)
            valid_end = train_end + int(len(dates) * valid_ratio)

            train_dates = dates[:train_end]
            val_dates = dates[train_end:valid_end]
            test_dates = dates[valid_end:]

            if len(train_dates) == 0 or len(test_dates) == 0:
                return self._base_result("error", "Split produced empty train or test period")

            train_data = self._slice_by_dates(data, train_dates)
            val_data = self._slice_by_dates(data, val_dates)
            test_data = self._slice_by_dates(data, test_dates)

            # Train strategy if needed
            if not strategy.is_fitted and strategy.strategy_type != StrategyType.RULE_BASED:
                try:
                    strategy.fit(train_data, val_data)
                except Exception:
                    return self._base_result("error", f"Training failed: {traceback.format_exc()}")

            # Generate signals
            # For rule-based strategies that need history, pass full data and slice
            idx = pd.IndexSlice
            try:
                # Pass full data for strategies that need lookback history
                full_signals = strategy.generate_signals(data)
                if not isinstance(full_signals, pd.Series):
                    raise TypeError("generate_signals must return pandas Series")
                # Slice signals to test period only
                signals = full_signals.loc[idx[test_dates, :]].copy()
            except Exception:
                return self._base_result("error", traceback.format_exc())

            # Compute strategy returns
            cost_bps = int(self.config.get("execution", {}).get("transaction_cost_bps", 10))
            strategy_returns = apply_costs(signals, test_data, cost_bps=cost_bps)

            # Compute forward returns for IC with configurable horizon
            backtest_cfg = self.config.get("backtest", {})
            ic_horizon = int(backtest_cfg.get("ic_horizon", 21))  # Default 21 days for momentum
            close = test_data["Close"].astype(float)
            forward_returns = close.groupby(level="ticker").shift(-ic_horizon) / close - 1.0

            # Risk-free rate and periods
            risk_free = float(backtest_cfg.get("risk_free_rate", 0.0))
            periods = int(backtest_cfg.get("periods_per_year", 252))

            # Compute strategy metrics
            strat_sharpe = sharpe_ratio(strategy_returns, risk_free_rate=risk_free, periods_per_year=periods)
            strat_sortino = sortino_ratio(strategy_returns, risk_free_rate=risk_free, periods_per_year=periods)
            strat_calmar = calmar_ratio(strategy_returns, periods_per_year=periods)
            strat_ic = information_coefficient(signals, forward_returns)
            strat_annual = annualized_return(strategy_returns, periods_per_year=periods)
            strat_mdd = max_drawdown(strategy_returns)
            daily_turn = annualized_turnover(signals) / periods
            strat_hit_rate = hit_rate(signals, forward_returns)
            strat_profit_factor = profit_factor(strategy_returns)

            # Compute IC at multiple horizons for reporting
            ic_horizons = backtest_cfg.get("ic_horizons", [1, 5, 21, 63])
            ic_by_horizon = {}
            for h in ic_horizons:
                fwd_h = close.groupby(level="ticker").shift(-h) / close - 1.0
                ic_h = information_coefficient(signals, fwd_h)
                ic_by_horizon[f"ic_{h}d"] = float(ic_h) if np.isfinite(ic_h) else np.nan

            # Run benchmarks
            bench = self._run_spy_benchmark(str(test_dates[0].date()), str(test_dates[-1].date()))
            spy_sharpe = bench["spy_sharpe"]
            spy_annual = bench["spy_annual_return"]
            spy_returns = bench["spy_returns"]

            alpha_vs_spy = strat_annual - spy_annual if np.isfinite(spy_annual) else np.nan
            beta_to_spy = beta_to_benchmark(strategy_returns, spy_returns) if not spy_returns.empty else np.nan

            # ML baseline
            ml = self._run_ml_baseline(train_data, test_data)

            # Sector exposure
            sector_summary = self._sector_mapper.sector_exposure_summary(signals)

            # Delisted count
            latest_date = dates[-1]
            latest_close = data.xs(latest_date, level="date")["Close"]
            delisted_count = int(latest_close.isna().sum())

            # Build result
            return {
                "status": "success",
                "message": "",
                # Strategy metrics
                "sharpe_ratio": float(strat_sharpe) if np.isfinite(strat_sharpe) else np.nan,
                "sortino_ratio": float(strat_sortino) if np.isfinite(strat_sortino) else np.nan,
                "calmar_ratio": float(strat_calmar) if np.isfinite(strat_calmar) else np.nan,
                "information_coefficient": float(strat_ic) if np.isfinite(strat_ic) else np.nan,
                **ic_by_horizon,  # IC at multiple horizons
                "annualized_return": float(strat_annual) if np.isfinite(strat_annual) else np.nan,
                "max_drawdown": float(strat_mdd) if np.isfinite(strat_mdd) else np.nan,
                "daily_turnover": float(daily_turn) if np.isfinite(daily_turn) else np.nan,
                "hit_rate": float(strat_hit_rate) if np.isfinite(strat_hit_rate) else np.nan,
                "profit_factor": float(strat_profit_factor) if np.isfinite(strat_profit_factor) else np.nan,
                # Benchmark metrics
                "alpha_vs_spy": float(alpha_vs_spy) if np.isfinite(alpha_vs_spy) else np.nan,
                "beta_to_spy": float(beta_to_spy) if np.isfinite(beta_to_spy) else np.nan,
                "spy_sharpe": float(spy_sharpe) if np.isfinite(spy_sharpe) else np.nan,
                "spy_annual_return": float(spy_annual) if np.isfinite(spy_annual) else np.nan,
                # ML baseline
                "xgb_sharpe": float(ml["xgb_sharpe"]) if np.isfinite(ml["xgb_sharpe"]) else np.nan,
                "logreg_sharpe": float(ml["logreg_sharpe"]) if np.isfinite(ml["logreg_sharpe"]) else np.nan,
                # Strategy metadata
                "strategy_type": strategy.strategy_type.value,
                "is_fitted": strategy.is_fitted,
                "hyperparameters": strategy.hyperparameters,
                "feature_names": strategy.feature_names,
                "feature_importance": strategy.feature_importance,
                # Data info
                "universe_size": int(data.index.get_level_values("ticker").nunique()),
                "delisted_count": delisted_count,
                "train_start": str(train_dates[0].date()),
                "train_end": str(train_dates[-1].date()),
                "val_start": str(val_dates[0].date()) if len(val_dates) > 0 else "",
                "val_end": str(val_dates[-1].date()) if len(val_dates) > 0 else "",
                "test_start": str(test_dates[0].date()),
                "test_end": str(test_dates[-1].date()),
                # Sector exposure
                "sector_exposure": sector_summary["sectors"],
                "top_sector": sector_summary["top_sector"],
                "sector_concentration": sector_summary["herfindahl"],
            }

        except Exception:
            return self._base_result("error", traceback.format_exc())


# Backward-compatible function wrapper
class Backtester(EnhancedBacktester):
    """Backward-compatible backtester."""

    def run(self) -> dict:
        """Run backtest using factor_path from config."""
        return super().run(strategy=None)