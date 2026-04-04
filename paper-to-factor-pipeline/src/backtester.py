import importlib
import sys
import traceback

import numpy as np
import pandas as pd

from src.benchmark import SPYBenchmark
from src.execution_model import apply_costs
from src.metrics import annualized_return, annualized_turnover, information_coefficient, max_drawdown, sharpe_ratio
from src.ml_baseline import MLBaseline
from src.prepare import DataLoader
from src.validator import validate_factor


class Backtester:
    def __init__(self, config: dict):
        self.config = config

    def _base_result(self, status: str, message: str) -> dict:
        return {
            "status": status,
            "message": message,
            "sharpe_ratio": np.nan,
            "information_coefficient": np.nan,
            "annualized_return": np.nan,
            "max_drawdown": np.nan,
            "daily_turnover": np.nan,
            "alpha_vs_spy": np.nan,
            "spy_sharpe": np.nan,
            "spy_annual_return": np.nan,
            "xgb_sharpe": np.nan,
            "logreg_sharpe": np.nan,
            "universe_size": 0,
            "delisted_count": 0,
            "train_start": "",
            "train_end": "",
            "test_start": "",
            "test_end": "",
        }

    def _slice_by_dates(self, data: pd.DataFrame, dates: pd.DatetimeIndex) -> pd.DataFrame:
        if len(dates) == 0:
            return data.iloc[0:0].copy()
        idx = pd.IndexSlice
        return data.loc[idx[dates, :], :].copy()

    def run(self) -> dict:
        try:
            data_cfg = self.config.get("data", {})
            start_date = data_cfg.get("start_date", "2015-01-01")
            end_date = data_cfg.get("end_date", "2023-12-31")

            loader = DataLoader()
            try:
                data = loader.load(start_date, end_date)
            except Exception:
                return self._base_result("error", traceback.format_exc())

            workflow_cfg = self.config.get("workflow", {})
            factor_path = workflow_cfg.get("factor_path", "sandbox/factor.py")
            validation = validate_factor(factor_path)
            if not validation.get("valid", False):
                msg = "; ".join(validation.get("issues", [])) or "Factor validation failed"
                return self._base_result("error", msg)

            sys.modules.pop("sandbox.factor", None)
            sys.modules.pop("sandbox", None)
            try:
                factor = importlib.import_module("sandbox.factor")
            except Exception:
                return self._base_result("error", traceback.format_exc())

            dates = pd.DatetimeIndex(sorted(data.index.get_level_values("date").unique()))
            if len(dates) < 30:
                return self._base_result("error", "Not enough dates to perform train/validation/test split")

            train_ratio = float(data_cfg.get("train_ratio", 0.60))
            valid_ratio = float(data_cfg.get("validation_ratio", 0.20))

            train_end = int(len(dates) * train_ratio)
            valid_end = train_end + int(len(dates) * valid_ratio)
            train_dates = dates[:train_end]
            _valid_dates = dates[train_end:valid_end]
            test_dates = dates[valid_end:]

            if len(train_dates) == 0 or len(test_dates) == 0:
                return self._base_result("error", "Split produced empty train or test period")

            train_data = self._slice_by_dates(data, train_dates)
            test_data = self._slice_by_dates(data, test_dates)

            try:
                signals = factor.generate_signals(test_data)
                if not isinstance(signals, pd.Series):
                    raise TypeError("generate_signals must return pandas Series")
                signals = signals.reindex(test_data.index)
            except Exception:
                return self._base_result("error", traceback.format_exc())

            cost_bps = int(self.config.get("execution", {}).get("transaction_cost_bps", 10))
            strategy_returns = apply_costs(signals, test_data, cost_bps=cost_bps)

            close = test_data["Close"].astype(float)
            forward_returns = close.groupby(level="ticker").shift(-1) / close - 1.0

            risk_free = float(self.config.get("backtest", {}).get("risk_free_rate", 0.0))
            periods = int(self.config.get("backtest", {}).get("periods_per_year", 252))

            strat_sharpe = sharpe_ratio(strategy_returns, risk_free_rate=risk_free, periods_per_year=periods)
            strat_ic = information_coefficient(signals, forward_returns)
            strat_annual = annualized_return(strategy_returns, periods_per_year=periods)
            strat_mdd = max_drawdown(strategy_returns)
            daily_turn = annualized_turnover(signals) / periods

            bench = SPYBenchmark(str(test_dates[0].date()), str(test_dates[-1].date())).run()
            spy_sharpe = float(bench.get("sharpe_ratio", np.nan))
            spy_annual = float(bench.get("annualized_return", np.nan))
            alpha_vs_spy = strat_annual - spy_annual if np.isfinite(spy_annual) else np.nan

            ml = MLBaseline(train_data=train_data, test_data=test_data).run()

            latest_date = dates[-1]
            latest_close = data.xs(latest_date, level="date")["Close"]
            delisted_count = int(latest_close.isna().sum())

            return {
                "status": "success",
                "message": "",
                "sharpe_ratio": float(strat_sharpe) if np.isfinite(strat_sharpe) else np.nan,
                "information_coefficient": float(strat_ic) if np.isfinite(strat_ic) else np.nan,
                "annualized_return": float(strat_annual) if np.isfinite(strat_annual) else np.nan,
                "max_drawdown": float(strat_mdd) if np.isfinite(strat_mdd) else np.nan,
                "daily_turnover": float(daily_turn) if np.isfinite(daily_turn) else np.nan,
                "alpha_vs_spy": float(alpha_vs_spy) if np.isfinite(alpha_vs_spy) else np.nan,
                "spy_sharpe": float(spy_sharpe) if np.isfinite(spy_sharpe) else np.nan,
                "spy_annual_return": float(spy_annual) if np.isfinite(spy_annual) else np.nan,
                "xgb_sharpe": float(ml.get("xgb_sharpe", np.nan)) if np.isfinite(ml.get("xgb_sharpe", np.nan)) else np.nan,
                "logreg_sharpe": float(ml.get("logreg_sharpe", np.nan)) if np.isfinite(ml.get("logreg_sharpe", np.nan)) else np.nan,
                "universe_size": int(data.index.get_level_values("ticker").nunique()),
                "delisted_count": delisted_count,
                "train_start": str(train_dates[0].date()),
                "train_end": str(train_dates[-1].date()),
                "test_start": str(test_dates[0].date()),
                "test_end": str(test_dates[-1].date()),
            }
        except Exception:
            return self._base_result("error", traceback.format_exc())
