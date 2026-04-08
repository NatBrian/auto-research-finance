---
name: model-train
description: Train ML models for trading strategies. Use when the user says "train model", "fit model", "train the strategy", or when the pipeline enters TRAINING phase for ML-based strategies.
version: 1.0
---

# Model Training Instructions

## Input
Read `sandbox/research_log.md` first to get:
- Selected paper's metadata and key_formula
- `strategy_type` (should be "ml_based")
- Current `hyperparameters` (if any)
- Current `feature_set` (if specified)

Read `config/settings.yaml` to get ML configuration:
- `ml.default_features`
- `ml.default_model`
- `ml.target_horizon`
- `ml.tune_hyperparams`
- Model-specific hyperparameters

## Steps

### 1. Load and Prepare Data

Load training data using the data loader:

```python
from src.prepare import DataLoader
from src.utils import load_config

config = load_config("config/settings.yaml")
loader = DataLoader()

data_cfg = config.get("data", {})
data = loader.load(
    data_cfg.get("start_date", "2015-01-01"),
    data_cfg.get("end_date", "2023-12-31"),
)

# Split into train/validation
train_ratio = data_cfg.get("train_ratio", 0.60)
valid_ratio = data_cfg.get("validation_ratio", 0.20)

dates = sorted(data.index.get_level_values("date").unique())
train_end = int(len(dates) * train_ratio)
valid_end = train_end + int(len(dates) * valid_ratio)

train_data = data.loc[pd.IndexSlice[dates[:train_end], :], :]
val_data = data.loc[pd.IndexSlice[dates[train_end:valid_end], :], :]
```

### 2. Configure Features

Determine which features to use:
- If `feature_set` is specified in research_log: Use those features
- Otherwise: Use `ml.default_features` from config

Verify features exist in `src/core/feature_registry.py` or will be built by the strategy.

### 3. Initialize Strategy

Load the strategy from `sandbox/factor.py`:

```python
import importlib
import sys

from src.strategies.base import MLStrategy

sys.modules.pop("sandbox.factor", None)
factor_module = importlib.import_module("sandbox.factor")

# Find the strategy class
strategy = None
for name in dir(factor_module):
    obj = getattr(factor_module, name)
    if isinstance(obj, type) and issubclass(obj, MLStrategy) and obj is not MLStrategy:
        strategy = obj()
        break

if strategy is None:
    raise ValueError("No MLStrategy found in sandbox/factor.py")
```

### 4. Train Model

Execute training with optional hyperparameter tuning:

```python
ml_cfg = config.get("ml", {})
tune = ml_cfg.get("tune_hyperparams", False)

if tune:
    # Perform cross-validation tuning
    strategy._tune_hyperparams = True
    strategy._cv_folds = ml_cfg.get("cv_folds", 5)

strategy.fit(train_data, val_data)
```

### 5. Save Model

Save trained model to disk:

```python
import os
os.makedirs("sandbox/models", exist_ok=True)
strategy.save("sandbox/models/trained_model.pkl")
```

### 6. Extract Metadata

Extract training results for logging:

```python
metadata = strategy.get_metadata()
# metadata contains:
# - hyperparameters (actual values used after tuning)
# - feature_names
# - feature_importance
```

## Output

Update `sandbox/research_log.md` with:

1. Set `is_fitted` to `true`
2. Update `hyperparameters` with actual values used
3. Update `feature_set` with list of features
4. Update `feature_importance` with importance scores
5. Set `model_path` to `"sandbox/models/trained_model.pkl"`

## Error Handling

If training fails:
1. Log the error to "Last Error" in research_log
2. Check common issues:
   - Insufficient data for feature engineering
   - NaN values in features
   - Model convergence issues
3. Suggest remediation actions

## Training Report

Output a summary:

```
═══════════════════════════════════════
MODEL TRAINING COMPLETE
═══════════════════════════════════════
Model Type: [model_type]
Training Period: [train_start] to [train_end]
Validation Period: [val_start] to [val_end]

Features Used ([N] total):
  1. [feature_1] - importance: [score]
  2. [feature_2] - importance: [score]
  ...

Hyperparameters:
  [key]: [value]
  ...

Model saved to: sandbox/models/trained_model.pkl
═══════════════════════════════════════
```