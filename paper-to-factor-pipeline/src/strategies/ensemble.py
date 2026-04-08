"""Ensemble strategies for combining multiple factors."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from src.strategies.base import BaseStrategy, StrategyType

logger = logging.getLogger(__name__)


class EnsembleStrategy(BaseStrategy):
    """
    Ensemble strategy that combines multiple strategies.

    Supports various combination methods:
    - mean: Average signals
    - median: Median signals
    - rank_average: Average of cross-sectional ranks
    - weighted: Weighted average with custom weights
    """

    strategy_type = StrategyType.ENSEMBLE

    def __init__(
        self,
        strategies: list[BaseStrategy],
        method: str = "mean",
        weights: list[float] | None = None,
        name: str = "Ensemble",
    ):
        """
        Initialize ensemble strategy.

        Args:
            strategies: List of strategies to combine.
            method: Combination method ("mean", "median", "rank_average", "weighted").
            weights: Weights for "weighted" method.
            name: Ensemble name.
        """
        super().__init__()
        self._strategies = strategies
        self._method = method
        self._weights = weights
        self._name = name

        if weights is not None and len(weights) != len(strategies):
            raise ValueError("Weights must match number of strategies")

        if method == "weighted" and weights is None:
            raise ValueError("Weights required for 'weighted' method")

        self._hyperparameters = {
            "method": method,
            "weights": weights,
            "num_strategies": len(strategies),
        }

    @property
    def name(self) -> str:
        return self._name

    def fit(
        self,
        train_data: pd.DataFrame,
        val_data: pd.DataFrame | None = None,
    ) -> "EnsembleStrategy":
        """
        Fit all strategies that require training.

        Args:
            train_data: Training data.
            val_data: Optional validation data.

        Returns:
            self
        """
        for strategy in self._strategies:
            if not strategy.is_fitted:
                strategy.fit(train_data, val_data)

        self._is_fitted = True
        return self

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate ensemble signals.

        Args:
            data: OHLCV data.

        Returns:
            Combined signal series.
        """
        self.validate_data(data)

        # Generate signals from each strategy
        signals_list = []
        for i, strategy in enumerate(self._strategies):
            try:
                sig = strategy.generate_signals(data)
                sig.name = f"strategy_{i}"
                signals_list.append(sig)
            except Exception as e:
                logger.warning(f"Strategy {i} failed: {e}")

        if not signals_list:
            return pd.Series(np.nan, index=data.index, name="signal")

        # Combine signals
        signals_df = pd.concat(signals_list, axis=1)

        if self._method == "mean":
            combined = signals_df.mean(axis=1, skipna=True)
        elif self._method == "median":
            combined = signals_df.median(axis=1, skipna=True)
        elif self._method == "rank_average":
            # Rank each strategy's signals, then average ranks
            ranks = []
            for col in signals_df.columns:
                rank = signals_df[col].groupby(level="date").rank(pct=True)
                ranks.append(rank)
            ranks_df = pd.concat(ranks, axis=1)
            combined = ranks_df.mean(axis=1, skipna=True)
        elif self._method == "weighted":
            weighted_sum = pd.Series(0.0, index=data.index)
            total_weight = 0.0
            for i, sig in enumerate(signals_list):
                w = self._weights[i]
                weighted_sum = weighted_sum.add(sig.fillna(0) * w, fill_value=0)
                total_weight += w
            combined = weighted_sum / total_weight
        else:
            raise ValueError(f"Unknown method: {self._method}")

        combined.name = "signal"
        return combined

    def get_metadata(self) -> dict[str, Any]:
        """Return ensemble metadata."""
        metadata = super().get_metadata()
        metadata["strategies"] = [
            {
                "type": s.strategy_type.value,
                "fitted": s.is_fitted,
                "hyperparameters": s.hyperparameters,
            }
            for s in self._strategies
        ]
        return metadata

    def __repr__(self) -> str:
        return f"EnsembleStrategy(method={self._method}, n={len(self._strategies)})"


class StackingEnsemble(BaseStrategy):
    """
    Stacking ensemble with meta-learner.

    Uses a meta-learner to optimally combine base strategy predictions.
    The meta-learner is trained on validation data to learn optimal weights.
    """

    strategy_type = StrategyType.ENSEMBLE

    def __init__(
        self,
        strategies: list[BaseStrategy],
        meta_model: str = "ridge",
        name: str = "StackingEnsemble",
    ):
        """
        Initialize stacking ensemble.

        Args:
            strategies: List of base strategies.
            meta_model: Meta-learner type ("ridge", "linear", "mean").
            name: Ensemble name.
        """
        super().__init__()
        self._strategies = strategies
        self._meta_model_type = meta_model
        self._name = name
        self._meta_model: Any = None
        self._meta_scaler: Any = None

        self._hyperparameters = {
            "meta_model": meta_model,
            "num_strategies": len(strategies),
        }

    def fit(
        self,
        train_data: pd.DataFrame,
        val_data: pd.DataFrame | None = None,
    ) -> "StackingEnsemble":
        """
        Fit base strategies and meta-learner.

        Args:
            train_data: Training data for base strategies.
            val_data: Validation data for meta-learner training.

        Returns:
            self
        """
        from sklearn.linear_model import Ridge, LinearRegression
        from sklearn.preprocessing import StandardScaler

        # Fit base strategies
        for strategy in self._strategies:
            if not strategy.is_fitted:
                strategy.fit(train_data, val_data)

        # Use validation data to train meta-learner
        if val_data is None:
            # Use part of train_data
            self._is_fitted = True
            return self

        # Generate base predictions on validation data
        val_signals = []
        for strategy in self._strategies:
            sig = strategy.generate_signals(val_data)
            val_signals.append(sig)

        val_signals_df = pd.concat(val_signals, axis=1)

        # Get forward returns as target
        close = val_data["Close"].astype(float)
        fwd_returns = close.groupby(level="ticker").shift(-5) / close - 1.0

        # Align
        valid_idx = val_signals_df.dropna().index.intersection(fwd_returns.dropna().index)
        if len(valid_idx) < 100:
            self._is_fitted = True
            return self

        X_meta = val_signals_df.loc[valid_idx].values
        y_meta = fwd_returns.loc[valid_idx].values

        # Scale meta features
        self._meta_scaler = StandardScaler()
        X_meta_scaled = self._meta_scaler.fit_transform(X_meta)

        # Train meta-learner
        if self._meta_model_type == "ridge":
            self._meta_model = Ridge(alpha=1.0)
        else:
            self._meta_model = LinearRegression()

        self._meta_model.fit(X_meta_scaled, y_meta)

        # Store weights as feature importance
        if hasattr(self._meta_model, "coef_"):
            self._feature_importance = {
                f"strategy_{i}": abs(w) for i, w in enumerate(self._meta_model.coef_)
            }

        self._is_fitted = True
        return self

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate stacked signals."""
        self.validate_data(data)

        # Generate base signals
        signals = []
        for strategy in self._strategies:
            sig = strategy.generate_signals(data)
            signals.append(sig)

        signals_df = pd.concat(signals, axis=1)
        valid_idx = signals_df.dropna().index

        if len(valid_idx) == 0:
            return pd.Series(np.nan, index=data.index, name="signal")

        if self._meta_model is None:
            # Fallback to mean
            return signals_df.mean(axis=1, skipna=True)

        X_meta = signals_df.loc[valid_idx].values
        X_meta_scaled = self._meta_scaler.transform(X_meta)

        predictions = self._meta_model.predict(X_meta_scaled)

        result = pd.Series(np.nan, index=data.index, name="signal")
        result.loc[valid_idx] = predictions

        return result

    def __repr__(self) -> str:
        return f"StackingEnsemble(meta={self._meta_model_type}, n={len(self._strategies)})"


def create_equal_weight_ensemble(
    strategies: list[BaseStrategy],
    name: str = "EqualWeightEnsemble",
) -> EnsembleStrategy:
    """Create an equal-weight ensemble of strategies."""
    n = len(strategies)
    weights = [1.0 / n] * n
    return EnsembleStrategy(strategies, method="weighted", weights=weights, name=name)


def create_rank_ensemble(
    strategies: list[BaseStrategy],
    name: str = "RankEnsemble",
) -> EnsembleStrategy:
    """Create a rank-average ensemble of strategies."""
    return EnsembleStrategy(strategies, method="rank_average", name=name)