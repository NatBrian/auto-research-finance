"""Abstract base class for trading strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class StrategyType(Enum):
    """Type of trading strategy."""

    RULE_BASED = "rule_based"
    ML_BASED = "ml_based"
    STATISTICAL = "statistical"
    ENSEMBLE = "ensemble"


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    Supports both rule-based (stateless) and ML-based (with training) strategies.
    """

    # Class-level attributes
    strategy_type: StrategyType = StrategyType.RULE_BASED
    _required_columns: list[str] = ["Open", "High", "Low", "Close", "Volume"]

    def __init__(self):
        self._is_fitted: bool = False
        self._hyperparameters: dict[str, Any] = {}
        self._feature_names: list[str] = []
        self._feature_importance: dict[str, float] = {}

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals from market data.

        Args:
            data: MultiIndex DataFrame with index levels (date, ticker).
                  Columns: Open, High, Low, Close, Volume.
                  All values are point-in-time — no future data leaks in.

        Returns:
            pd.Series with the same MultiIndex (date, ticker).
            Values are signal strengths (floats, not restricted to -1/0/1).
            Higher values = stronger long signal.
            NaN = no position for that ticker on that date.
        """
        pass

    def fit(
        self,
        train_data: pd.DataFrame,
        val_data: pd.DataFrame | None = None,
    ) -> "BaseStrategy":
        """
        Optional training phase for ML-based strategies.

        Override this method for strategies that require training.
        Default implementation is a no-op for rule-based strategies.

        Args:
            train_data: Training data with same schema as generate_signals.
            val_data: Optional validation data for early stopping.

        Returns:
            self (for method chaining)
        """
        self._is_fitted = True
        return self

    def save(self, path: str | Path) -> None:
        """
        Save model state to disk.

        Override for strategies with learned parameters.
        Default implementation does nothing (rule-based strategies don't need saving).
        """
        pass

    def load(self, path: str | Path) -> "BaseStrategy":
        """
        Load model state from disk.

        Override for strategies with learned parameters.
        Default implementation returns self unchanged.
        """
        return self

    def validate_data(self, data: pd.DataFrame) -> None:
        """
        Validate that input data has required columns and structure.

        Args:
            data: Input DataFrame to validate.

        Raises:
            ValueError: If data is missing required columns or has wrong structure.
        """
        if not isinstance(data, pd.DataFrame):
            raise ValueError(f"Expected pandas DataFrame, got {type(data)}")

        if not isinstance(data.index, pd.MultiIndex):
            raise ValueError("Data must have MultiIndex with (date, ticker) levels")

        if data.index.names != ["date", "ticker"]:
            raise ValueError(
                f"Data index must be named ['date', 'ticker'], got {data.index.names}"
            )

        missing = [c for c in self._required_columns if c not in data.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

    @property
    def is_fitted(self) -> bool:
        """Return True if strategy has been trained."""
        return self._is_fitted

    @property
    def hyperparameters(self) -> dict[str, Any]:
        """Return hyperparameters for logging."""
        return self._hyperparameters.copy()

    @hyperparameters.setter
    def hyperparameters(self, value: dict[str, Any]) -> None:
        self._hyperparameters = value

    @property
    def feature_names(self) -> list[str]:
        """Return feature names used (for ML strategies)."""
        return self._feature_names.copy()

    @feature_names.setter
    def feature_names(self, value: list[str]) -> None:
        self._feature_names = value

    @property
    def feature_importance(self) -> dict[str, float]:
        """Return feature importance scores (for ML strategies)."""
        return self._feature_importance.copy()

    @feature_importance.setter
    def feature_importance(self, value: dict[str, float]) -> None:
        self._feature_importance = value

    def get_metadata(self) -> dict[str, Any]:
        """
        Return strategy metadata for logging and comparison.

        Returns:
            Dictionary with strategy type, hyperparameters, features, etc.
        """
        return {
            "strategy_type": self.strategy_type.value,
            "is_fitted": self._is_fitted,
            "hyperparameters": self._hyperparameters,
            "feature_names": self._feature_names,
            "feature_importance": self._feature_importance,
        }

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"type={self.strategy_type.value}, "
            f"fitted={self._is_fitted})"
        )


class RuleBasedStrategy(BaseStrategy):
    """
    Base class for rule-based (stateless) strategies.

    These strategies don't require training and generate signals
    directly from input data using deterministic rules.
    """

    strategy_type = StrategyType.RULE_BASED

    def __init__(self):
        super().__init__()
        # Rule-based strategies are always "fitted" by default
        self._is_fitted = True


class MLStrategy(BaseStrategy):
    """
    Base class for machine learning-based strategies.

    These strategies require training on historical data before
    generating signals.
    """

    strategy_type = StrategyType.ML_BASED

    def __init__(self):
        super().__init__()
        self._model: Any = None
        self._scaler: Any = None

    @abstractmethod
    def _build_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Build feature matrix from raw market data.

        Args:
            data: Raw OHLCV data.

        Returns:
            DataFrame with engineered features.
        """
        pass

    @abstractmethod
    def _build_target(self, data: pd.DataFrame) -> pd.Series:
        """
        Build target variable from raw market data.

        Args:
            data: Raw OHLCV data.

        Returns:
            Series with target values.
        """
        pass

    def save(self, path: str | Path) -> None:
        """Save model and scaler to disk."""
        import joblib

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        save_dict = {
            "model": self._model,
            "scaler": self._scaler,
            "hyperparameters": self._hyperparameters,
            "feature_names": self._feature_names,
            "feature_importance": self._feature_importance,
        }
        joblib.dump(save_dict, path)

    def load(self, path: str | Path) -> "MLStrategy":
        """Load model and scaler from disk."""
        import joblib

        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        save_dict = joblib.load(path)
        self._model = save_dict.get("model")
        self._scaler = save_dict.get("scaler")
        self._hyperparameters = save_dict.get("hyperparameters", {})
        self._feature_names = save_dict.get("feature_names", [])
        self._feature_importance = save_dict.get("feature_importance", {})
        self._is_fitted = True

        return self


class StatisticalStrategy(BaseStrategy):
    """
    Base class for statistical time-series strategies.

    These strategies use statistical models (ARIMA, GARCH, etc.)
    for signal generation.
    """

    strategy_type = StrategyType.STATISTICAL

    def __init__(self):
        super().__init__()
        self._model: Any = None