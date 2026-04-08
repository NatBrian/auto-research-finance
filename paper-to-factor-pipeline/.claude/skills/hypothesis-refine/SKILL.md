---
name: hypothesis-refine
description: Diagnose backtest failure and apply targeted refinement to sandbox/factor.py. Use when the user says "refine hypothesis", "fix the backtest", "diagnose error", "improve Sharpe", "fix IC", or "adjust the factor".
version: 3.0
---

# Hypothesis Refinement Instructions (Hybrid Architecture)

## Input
Read `sandbox/research_log.md` first to get:
- Last Backtest Result (full JSON)
- Last Error (if any)
- Refinement Actions Taken (to avoid repeating the same fix)
- Current iteration number
- **strategy_type** (rule_based, ml_based, statistical, ensemble)

## Strategy-Type-Specific Refinement

First, check `strategy_type` and apply the appropriate refinement branch.

---

## FOR RULE-BASED STRATEGIES

### Branch A: Code Error
**Condition**: `status == "error"` in Last Backtest Result

Sub-branch A1 — SyntaxError or IndentationError:
- Read `sandbox/factor.py`
- Fix the syntax issue directly
- Log action: "A1: Fixed syntax error: [description]"

Sub-branch A2 — ValueError (wrong column or index):
- Re-read `data/manifest.json`
- Correct column names or index access patterns in `sandbox/factor.py`
- Log action: "A2: Fixed column/index error: [description]"

Sub-branch A3 — Other RuntimeError:
- Read the full traceback in "Last Error"
- Fix the specific line that raised the exception
- Add a defensive check to prevent recurrence
- Log action: "A3: Fixed runtime error: [description]"

### Branch B: Negative or Near-Zero IC (IC < 0.01)
**Condition**: `information_coefficient` < 0.01

Sub-branch B1 — IC is significantly negative (< -0.05):
- Invert the signal by multiplying by -1
- Log action: "B1: Inverted signal direction"

Sub-branch B2 — IC is near zero (-0.05 to 0.01):
- Extend the lookback window by 2x (e.g., 20 days → 40 days)
- Log action: "B2: Extended lookback to [N] days"

### Branch C: IC Acceptable but Sharpe Low (IC > 0.03, Sharpe < 0.8)
**Condition**: `information_coefficient` > 0.03 AND `sharpe_ratio` < 0.8

Sub-branch C1 — High Turnover (> 20% daily):
- Add 5-day signal smoothing before ranking
- Log action: "C1: Added 5-day signal smoothing"

Sub-branch C2 — Normal Turnover:
- Add volatility filter at 2x median threshold
- Log action: "C2: Added volatility filter"

### Branch D: Sharpe OK but Underperforms SPY (Sharpe > 0.8, alpha_vs_spy < 0)
**Condition**: `sharpe_ratio` > 0.8 AND `alpha_vs_spy` <= 0.0

Sub-branch D1:
- Convert to long-only with `.clip(lower=0)`
- Log action: "D1: Converted to long-only"

### Branch E: Borderline Metrics
**Condition**: All metrics close but not meeting thresholds

- Add cross-sectional z-score normalization:
  `signal = signal.groupby(level='date').transform(lambda x: (x - x.mean()) / (x.std() + 1e-8))`
- Log action: "E1: Added cross-sectional z-score normalization"

### Branch F: Catch-All
- Extend lookback by 1.5x
- Log action: "F1: Extended lookback (catch-all)"

---

## FOR ML-BASED STRATEGIES

### Branch M-A: Training Error
**Condition**: `status == "error"` and error mentions training

Sub-branch M-A1 — Convergence Error:
- Reduce learning rate by 50%
- Increase max_iter or n_estimators
- Log action: "M-A1: Reduced learning rate, increased iterations"

Sub-branch M-A2 — NaN in Features:
- Check feature engineering for division by zero
- Add .replace(0.0, np.nan) or small epsilon
- Log action: "M-A2: Fixed NaN in feature computation"

### Branch M-B: Overfitting (Train >> Test)
**Condition**: Train Sharpe >> Test Sharpe (> 0.5 difference)

Sub-branch M-B1:
- Reduce max_depth by 1
- Increase min_samples_split or add regularization
- Log action: "M-B1: Added regularization to reduce overfitting"

Sub-branch M-B2:
- Remove least important features (bottom 20%)
- Check feature_importance from research_log
- Log action: "M-B2: Removed low-importance features"

### Branch M-C: Underfitting (Both Train and Test Poor)
**Condition**: Train Sharpe < 0.5 AND Test Sharpe < 0.5

Sub-branch M-C1:
- Increase max_depth by 1
- Increase n_estimators by 50%
- Log action: "M-C1: Increased model complexity"

Sub-branch M-C2:
- Add more features from feature_registry
- Consider extended_features from config
- Log action: "M-C2: Added more features"

### Branch M-D: IC Issues
**Condition**: `information_coefficient` < 0.02

Sub-branch M-D1:
- Change target horizon (try 1d, 5d, 20d)
- Log action: "M-D1: Changed target horizon to [N] days"

Sub-branch M-D2:
- Re-train with hyperparameter tuning enabled
- Set tune_hyperparams = True in config
- Log action: "M-D2: Enabled hyperparameter tuning"

### Branch M-E: High Beta to SPY
**Condition**: `beta_to_spy` > 1.5

- Add sector neutralization:
  `signal = signal.groupby(level='date').transform(lambda x: x - x.mean())`
- Log action: "M-E1: Added sector neutralization"

### Branch M-F: Catch-All for ML
- Retrain with different random seed
- Add cross-validation
- Log action: "M-F1: Retrained with new random seed"

---

## FOR STATISTICAL STRATEGIES

### Branch S-A: Model Convergence Issues
**Condition**: Error related to model fitting

- Increase sample size requirement
- Add fallback to simpler model
- Log action: "S-A1: Added fallback for convergence issues"

### Branch S-B: Regime Change
**Condition**: Rolling metrics show sudden drops

- Reduce lookback window
- Add regime detection filter
- Log action: "S-B1: Added regime filter"

### Branch S-C: Poor IC
**Condition**: `information_coefficient` < 0.02

- Adjust window parameters
- Add rolling recalibration
- Log action: "S-C1: Added rolling recalibration"

---

## FOR ENSEMBLE STRATEGIES

### Branch E-A: Component Failure
**Condition**: One or more components failed

- Remove failing component
- Re-weight remaining components
- Log action: "E-A1: Removed failing component"

### Branch E-B: Correlated Signals
**Condition**: All components have similar performance

- Add diversity by including different strategy types
- Change ensemble method (try rank_average)
- Log action: "E-B1: Changed ensemble method"

### Branch E-C: Poor Overall Performance
**Condition**: Ensemble underperforms individual components

- Use stacking instead of simple averaging
- Train meta-learner on validation data
- Log action: "E-C1: Switched to stacking ensemble"

---

## After Applying Fix

1. Re-read `sandbox/factor.py` to confirm the change was applied correctly.
2. Confirm no new look-ahead bias was introduced.
3. For ML strategies: May need to retrain (update `is_fitted` to false in research_log).
4. Append the log action to "Refinement Actions Taken" in `sandbox/research_log.md`.
5. Do NOT apply more than one fix per iteration.

## Output
Modified `sandbox/factor.py` with exactly one targeted change applied.
Write updated `sandbox/research_log.md` as the last action.