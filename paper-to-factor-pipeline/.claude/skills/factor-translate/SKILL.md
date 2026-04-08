---
name: factor-translate
description: Translate a selected paper's signal into executable Python code. Use when the user says "translate the paper", "write the factor", "convert signal to code", "implement the formula", or "generate factor code".
version: 3.0
---

# Factor Translation Instructions (Hybrid Architecture)

## Input
Read `sandbox/research_log.md` first to get:
- Selected paper's arxiv_id, title, abstract_summary, and key_formula
- `strategy_type` (rule_based, ml_based, statistical, or ensemble)

Read `data/manifest.json` to understand the exact column names and index structure available.

## Strategy Type Detection

Based on `strategy_type` from research_log, generate the appropriate code structure:

---

## Type A: Rule-Based Strategy (strategy_type == "rule_based")

Generate a standalone `generate_signals` function OR a `RuleBasedStrategy` subclass.

### Template for Simple Function:

```python
"""
Factor: [Paper Title]
ArXiv ID: [arxiv_id]
Strategy Type: rule_based
Signal Type: [signal type: momentum, mean-reversion, volatility, etc.]
Lookback: [lookback period in days]
"""

import pandas as pd
import numpy as np


def generate_signals(data: pd.DataFrame) -> pd.Series:
    """
    Generate trading signals from market data.

    Args:
        data: MultiIndex DataFrame with index levels (date, ticker).
              Columns: Open, High, Low, Close, Volume (per manifest.json).
              All values are point-in-time — no future data leaks in.

    Returns:
        pd.Series with the same MultiIndex (date, ticker).
        Values are signal strengths (floats, not restricted to -1/0/1).
        Higher values = stronger long signal.
        NaN = no position for that ticker on that date.
    """
    # --- Input validation ---
    required_cols = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required_cols if c not in data.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # --- Signal computation ---
    # Critical rules:
    # 1. Use .shift(1) before any signal computation to avoid look-ahead bias
    # 2. Use groupby(level='ticker') for any ticker-level operations
    # 3. Cross-sectional rank at the end: signal.groupby(level='date').rank(pct=True)
    # 4. Fill NaN from insufficient history with np.nan, not 0
    # 5. Do NOT use any data after the current row

    signals = pd.Series(np.nan, index=data.index, name="signal")

    # [IMPLEMENT PAPER'S FORMULA HERE]

    return signals
```

### Template for RuleBasedStrategy Class:

```python
"""
Factor: [Paper Title]
ArXiv ID: [arxiv_id]
Strategy Type: rule_based
"""

import pandas as pd
import numpy as np
from src.strategies.base import RuleBasedStrategy


class PaperFactor(RuleBasedStrategy):
    """[Paper title] implementation."""

    def __init__(self, lookback: int = [DEFAULT], skip: int = [DEFAULT]):
        super().__init__()
        self._lookback = lookback
        self._skip = skip
        self._hyperparameters = {
            "lookback": lookback,
            "skip": skip,
        }

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate [strategy name] signals."""
        self.validate_data(data)

        # [IMPLEMENT PAPER'S FORMULA HERE]

        return signals
```

---

## Type B: ML-Based Strategy (strategy_type == "ml_based")

Generate an `MLStrategy` subclass with feature engineering and model training.

### Template:

```python
"""
Factor: [Paper Title]
ArXiv ID: [arxiv_id]
Strategy Type: ml_based
Model: [model type: xgboost, random_forest, neural_network, etc.]
"""

import pandas as pd
import numpy as np
from typing import Any
from src.strategies.base import MLStrategy


class PaperMLStrategy(MLStrategy):
    """[Paper title] ML-based implementation."""

    def __init__(
        self,
        model_type: str = "xgboost",
        target_horizon: int = [DEFAULT],
        hyperparams: dict | None = None,
    ):
        super().__init__()
        self._model_type = model_type
        self._target_horizon = target_horizon
        self._hyperparameters = {
            "model_type": model_type,
            "target_horizon": target_horizon,
            **(hyperparams or {}),
        }

    def _build_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Build features as described in the paper.

        [LIST FEATURES FROM PAPER]
        """
        close = data["Close"].astype(float)
        volume = data["Volume"].astype(float)

        features = {}

        # [IMPLEMENT PAPER'S FEATURES HERE]
        # Example:
        # features["ret_20d"] = np.log(
        #     close.groupby(level="ticker").shift(1) /
        #     close.groupby(level="ticker").shift(21)
        # )

        self._feature_names = list(features.keys())
        return pd.DataFrame(features)

    def _build_target(self, data: pd.DataFrame) -> pd.Series:
        """Build target: [describe target from paper]."""
        close = data["Close"].astype(float)
        # [IMPLEMENT TARGET]
        return target

    def fit(
        self,
        train_data: pd.DataFrame,
        val_data: pd.DataFrame | None = None,
    ) -> "PaperMLStrategy":
        """Train the model."""
        # [IMPLEMENT TRAINING LOGIC]
        # Use self._create_model() or custom model
        self._is_fitted = True
        return self

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals using trained model."""
        self.validate_data(data)

        if not self._is_fitted:
            raise RuntimeError("Model must be fitted first")

        # [IMPLEMENT SIGNAL GENERATION]
        return signals
```

---

## Type C: Statistical Strategy (strategy_type == "statistical")

Generate a `StatisticalStrategy` subclass for time-series models.

### Template:

```python
"""
Factor: [Paper Title]
ArXiv ID: [arxiv_id]
Strategy Type: statistical
Model: [ARIMA, GARCH, cointegration, etc.]
"""

import pandas as pd
import numpy as np
from src.strategies.base import StatisticalStrategy


class PaperStatisticalStrategy(StatisticalStrategy):
    """[Paper title] statistical implementation."""

    def __init__(self, window: int = [DEFAULT], **kwargs):
        super().__init__()
        self._window = window
        self._hyperparameters = {"window": window, **kwargs}

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Generate signals from statistical model."""
        self.validate_data(data)

        # [IMPLEMENT STATISTICAL MODEL]
        # Examples: z-score mean reversion, cointegration spread, etc.

        return signals
```

---

## Post-Generation Checklist

After writing `sandbox/factor.py`, perform a self-review:

1. **Look-ahead bias check**: Confirm no `.shift(-1)` or negative shifts
2. **Return type check**: Confirm pd.Series with correct MultiIndex
3. **NaN handling**: Confirm explicit NaN handling (not filling with 0)
4. **No external dependencies**: Function should not read external files
5. **Strategy type match**: Code matches the `strategy_type` from research_log
6. **Hyperparameters tracked**: All configurable params in `_hyperparameters`
7. **Feature names tracked**: For ML strategies, set `_feature_names`

## Output
Write final status updates to `sandbox/research_log.md`:
- Update `feature_set` with list of features (for ML)
- Update `hyperparameters` with default values
- Write the factor file to `sandbox/factor.py`