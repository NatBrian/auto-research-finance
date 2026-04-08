"""Machine learning-based trading strategies."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import StandardScaler

from src.core.feature_registry import FeatureRegistry, DEFAULT_FEATURES
from src.strategies.base import MLStrategy

try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None


class TreeBasedStrategy(MLStrategy):
    """
    Tree-based ML strategy (XGBoost or Random Forest).

    This strategy:
    1. Engineers features from OHLCV data
    2. Trains a classifier on forward returns
    3. Uses prediction probability as trading signal
    """

    def __init__(
        self,
        model_type: str = "xgboost",
        features: list[str] | None = None,
        target_horizon: int = 5,
        hyperparams: dict[str, Any] | None = None,
        tune_hyperparams: bool = False,
        cv_folds: int = 5,
        random_state: int = 42,
    ):
        """
        Initialize tree-based strategy.

        Args:
            model_type: "xgboost" or "random_forest".
            features: List of feature names from FeatureRegistry.
            target_horizon: Forward return horizon in days.
            hyperparams: Model hyperparameters.
            tune_hyperparams: Whether to perform cross-validation tuning.
            cv_folds: Number of CV folds for tuning.
            random_state: Random seed for reproducibility.
        """
        super().__init__()
        self._model_type = model_type
        self._features = features or DEFAULT_FEATURES
        self._target_horizon = target_horizon
        self._tune_hyperparams = tune_hyperparams
        self._cv_folds = cv_folds
        self._random_state = random_state

        # Default hyperparameters
        self._hyperparameters = {
            "model_type": model_type,
            "target_horizon": target_horizon,
            "features": self._features,
        }

        if model_type == "xgboost":
            self._hyperparameters.update(hyperparams or {
                "n_estimators": 100,
                "max_depth": 3,
                "learning_rate": 0.1,
            })
        else:  # random_forest
            self._hyperparameters.update(hyperparams or {
                "n_estimators": 100,
                "max_depth": 5,
                "min_samples_split": 10,
            })

        self._feature_names = self._features

    def _build_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Build feature matrix using FeatureRegistry."""
        return FeatureRegistry.build_features(data, self._features)

    def _build_target(self, data: pd.DataFrame) -> pd.Series:
        """Build target: forward returns binned into quintiles."""
        close = data["Close"].astype(float)
        fwd = close.groupby(level="ticker").shift(-self._target_horizon) / close - 1.0
        return fwd

    def _create_model(self) -> Any:
        """Create model instance with current hyperparameters."""
        if self._model_type == "xgboost":
            if XGBClassifier is None:
                raise ImportError("XGBoost not installed. Use random_forest instead.")
            return XGBClassifier(
                n_estimators=self._hyperparameters.get("n_estimators", 100),
                max_depth=self._hyperparameters.get("max_depth", 3),
                learning_rate=self._hyperparameters.get("learning_rate", 0.1),
                random_state=self._random_state,
                eval_metric="mlogloss",
            )
        else:  # random_forest
            return RandomForestClassifier(
                n_estimators=self._hyperparameters.get("n_estimators", 100),
                max_depth=self._hyperparameters.get("max_depth", 5),
                min_samples_split=self._hyperparameters.get("min_samples_split", 10),
                random_state=self._random_state,
                n_jobs=-1,
            )

    def fit(
        self,
        train_data: pd.DataFrame,
        val_data: pd.DataFrame | None = None,
    ) -> "TreeBasedStrategy":
        """
        Train the model on historical data.

        Args:
            train_data: Training OHLCV data.
            val_data: Optional validation data for early stopping.

        Returns:
            self (for chaining)
        """
        # Build features and target
        train_features = self._build_features(train_data)
        train_target = self._build_target(train_data)

        # Drop NaN and align
        train_target_valid = train_target.dropna()
        if train_target_valid.empty:
            raise ValueError("No valid training targets")

        # Bin into quintiles (0-indexed for XGBoost compatibility)
        quantiles = train_target_valid.quantile([0.2, 0.4, 0.6, 0.8]).values
        bins = [-np.inf, *quantiles.tolist(), np.inf]
        labels = [0, 1, 2, 3, 4]  # 0-indexed for XGBoost

        train_target_binned = pd.cut(train_target, bins=bins, labels=labels).astype(float)

        # Create training dataset
        train_ds = train_features.copy()
        train_ds["target"] = train_target_binned
        train_ds = train_ds.dropna()

        if train_ds.empty:
            raise ValueError("Training dataset is empty after feature engineering")

        X_train = train_ds.drop(columns=["target"])
        y_train = train_ds["target"].astype(int)

        # Scale features
        self._scaler = StandardScaler()
        X_train_scaled = self._scaler.fit_transform(X_train)

        # Hyperparameter tuning
        if self._tune_hyperparams:
            self._tune(X_train_scaled, y_train)

        # Create and train model
        self._model = self._create_model()

        if self._model_type == "xgboost" and val_data is not None:
            # Use validation data for early stopping
            val_features = self._build_features(val_data)
            val_target = self._build_target(val_data)
            val_target_binned = pd.cut(val_target, bins=bins, labels=labels).astype(float)

            val_ds = val_features.copy()
            val_ds["target"] = val_target_binned
            val_ds = val_ds.dropna()

            if not val_ds.empty:
                X_val = val_ds.drop(columns=["target"])
                y_val = val_ds["target"].astype(int)
                X_val_scaled = self._scaler.transform(X_val)

                self._model.fit(
                    X_train_scaled,
                    y_train,
                    eval_set=[(X_val_scaled, y_val)],
                    verbose=False,
                )
            else:
                self._model.fit(X_train_scaled, y_train)
        else:
            self._model.fit(X_train_scaled, y_train)

        # Extract feature importance
        self._extract_feature_importance()

        self._is_fitted = True
        return self

    def _tune(self, X: np.ndarray, y: np.ndarray) -> None:
        """Perform basic hyperparameter tuning via cross-validation."""
        tscv = TimeSeriesSplit(n_splits=self._cv_folds)

        best_score = -np.inf
        best_params = {}

        # Simple grid search
        param_grid = {
            "xgboost": [
                {"max_depth": 3, "learning_rate": 0.1},
                {"max_depth": 5, "learning_rate": 0.05},
                {"max_depth": 7, "learning_rate": 0.01},
            ],
            "random_forest": [
                {"max_depth": 3, "min_samples_split": 20},
                {"max_depth": 5, "min_samples_split": 10},
                {"max_depth": 7, "min_samples_split": 5},
            ],
        }

        for params in param_grid.get(self._model_type, []):
            # Create model with these params
            test_params = self._hyperparameters.copy()
            test_params.update(params)

            temp_model = self._create_model()
            temp_model.set_params(**{k: v for k, v in params.items() if hasattr(temp_model, k)})

            try:
                scores = cross_val_score(temp_model, X, y, cv=tscv, scoring="accuracy")
                mean_score = scores.mean()

                if mean_score > best_score:
                    best_score = mean_score
                    best_params = params
            except Exception:
                continue

        if best_params:
            self._hyperparameters.update(best_params)

    def _extract_feature_importance(self) -> None:
        """Extract feature importance from trained model."""
        if self._model is None:
            return

        try:
            if hasattr(self._model, "feature_importances_"):
                importance = self._model.feature_importances_
                self._feature_importance = dict(zip(self._features, importance))
            elif hasattr(self._model, "coef_"):
                # For linear models
                importance = np.abs(self._model.coef_).mean(axis=0)
                self._feature_importance = dict(zip(self._features, importance))
        except Exception:
            pass

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate trading signals using trained model.

        Args:
            data: OHLCV data for signal generation.

        Returns:
            Signal series (probability of being in top quintile).
        """
        self.validate_data(data)

        if not self._is_fitted:
            raise RuntimeError("Model must be fitted before generating signals")

        # Build features
        features = self._build_features(data)

        # Get rows with all features available
        valid_idx = features.dropna().index
        if len(valid_idx) == 0:
            return pd.Series(np.nan, index=data.index, name="signal")

        X = features.loc[valid_idx]
        X_scaled = self._scaler.transform(X)

        # Predict probability of being in top quintile (class 4 = highest)
        proba = self._model.predict_proba(X_scaled)

        # Get index of class 4 (top quintile, 0-indexed)
        class_to_idx = {c: i for i, c in enumerate(self._model.classes_)}
        top_class_idx = class_to_idx.get(4, len(self._model.classes_) - 1)

        # Create signal series
        signals = pd.Series(np.nan, index=data.index, name="signal")
        signals.loc[valid_idx] = proba[:, top_class_idx]

        return signals

    def __repr__(self) -> str:
        return (
            f"TreeBasedStrategy("
            f"type={self._model_type}, "
            f"features={len(self._features)}, "
            f"fitted={self._is_fitted})"
        )


class LogisticRegressionStrategy(MLStrategy):
    """
    Logistic regression baseline strategy.

    Simple, interpretable linear model for comparison.
    """

    def __init__(
        self,
        features: list[str] | None = None,
        target_horizon: int = 5,
        max_iter: int = 1000,
        random_state: int = 42,
    ):
        """
        Initialize logistic regression strategy.

        Args:
            features: List of feature names.
            target_horizon: Forward return horizon.
            max_iter: Maximum iterations for solver.
            random_state: Random seed.
        """
        super().__init__()
        self._features = features or DEFAULT_FEATURES
        self._target_horizon = target_horizon
        self._max_iter = max_iter
        self._random_state = random_state

        self._hyperparameters = {
            "target_horizon": target_horizon,
            "features": self._features,
            "max_iter": max_iter,
        }
        self._feature_names = self._features

    def _build_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """Build feature matrix."""
        return FeatureRegistry.build_features(data, self._features)

    def _build_target(self, data: pd.DataFrame) -> pd.Series:
        """Build target: forward returns."""
        close = data["Close"].astype(float)
        return close.groupby(level="ticker").shift(-self._target_horizon) / close - 1.0

    def fit(
        self,
        train_data: pd.DataFrame,
        val_data: pd.DataFrame | None = None,
    ) -> "LogisticRegressionStrategy":
        """Train the logistic regression model."""
        train_features = self._build_features(train_data)
        train_target = self._build_target(train_data)

        train_target_valid = train_target.dropna()
        if train_target_valid.empty:
            raise ValueError("No valid training targets")

        # Bin into quintiles (0-indexed for XGBoost compatibility)
        quantiles = train_target_valid.quantile([0.2, 0.4, 0.6, 0.8]).values
        bins = [-np.inf, *quantiles.tolist(), np.inf]
        labels = [0, 1, 2, 3, 4]  # 0-indexed for XGBoost

        train_target_binned = pd.cut(train_target, bins=bins, labels=labels).astype(float)

        train_ds = train_features.copy()
        train_ds["target"] = train_target_binned
        train_ds = train_ds.dropna()

        if train_ds.empty:
            raise ValueError("Training dataset is empty")

        X_train = train_ds.drop(columns=["target"])
        y_train = train_ds["target"].astype(int)

        self._scaler = StandardScaler()
        X_train_scaled = self._scaler.fit_transform(X_train)

        self._model = LogisticRegression(
            max_iter=self._max_iter,
            random_state=self._random_state,
        )
        self._model.fit(X_train_scaled, y_train)

        # Extract coefficients as feature importance
        if hasattr(self._model, "coef_"):
            importance = np.abs(self._model.coef_).mean(axis=0)
            self._feature_importance = dict(zip(self._features, importance))

        self._is_fitted = True
        return self

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals using trained model."""
        self.validate_data(data)

        if not self._is_fitted:
            raise RuntimeError("Model must be fitted first")

        features = self._build_features(data)
        valid_idx = features.dropna().index

        if len(valid_idx) == 0:
            return pd.Series(np.nan, index=data.index, name="signal")

        X = features.loc[valid_idx]
        X_scaled = self._scaler.transform(X)

        proba = self._model.predict_proba(X_scaled)

        class_to_idx = {c: i for i, c in enumerate(self._model.classes_)}
        top_class_idx = class_to_idx.get(5, len(self._model.classes_) - 1)

        signals = pd.Series(np.nan, index=data.index, name="signal")
        signals.loc[valid_idx] = proba[:, top_class_idx]

        return signals

    def __repr__(self) -> str:
        return f"LogisticRegressionStrategy(fitted={self._is_fitted})"