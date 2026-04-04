---
name: hypothesis-refine
description: Diagnose backtest failure and apply targeted refinement to sandbox/factor.py. Use when the user says "refine hypothesis", "fix the backtest", "diagnose error", "improve Sharpe", "fix IC", or "adjust the factor".
---

# Hypothesis Refinement Instructions

## Input
Read `sandbox/research_log.md` first to get:
- Last Backtest Result (full JSON)
- Last Error (if any)
- Refinement Actions Taken (to avoid repeating the same fix)
- Current iteration number

## Diagnosis Decision Tree

Work through this tree in order. Apply the FIRST matching fix.

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
- This tests if the paper's hypothesis is directionally correct but the implementation is inverted
- Log action: "B1: Inverted signal direction"

Sub-branch B2 — IC is near zero (-0.05 to 0.01):
- The signal has no predictive power as currently implemented
- Extend the lookback window by 2x (e.g., 20 days → 40 days)
- Log action: "B2: Extended lookback to [N] days"

### Branch C: IC is Acceptable but Sharpe is Low (IC > 0.03, Sharpe < 0.8)
**Condition**: `information_coefficient` > 0.03 AND `sharpe_ratio` < 0.8

Sub-branch C1 — High Turnover (> 20% daily):
- Add a signal smoothing step: replace raw signal with its 5-day rolling mean before ranking
- This reduces transaction costs which are dragging down Sharpe
- Log action: "C1: Added 5-day signal smoothing to reduce turnover"

Sub-branch C2 — Normal Turnover but Low Sharpe:
- Add a volatility filter: zero out signals for tickers where 20-day rolling volatility > 2x universe median
- This removes high-risk positions that are degrading risk-adjusted returns
- Log action: "C2: Added volatility filter at 2x median threshold"

### Branch D: Sharpe Acceptable but Underperforms SPY (Sharpe > 0.8, alpha_vs_spy < 0)
**Condition**: `sharpe_ratio` > 0.8 AND `alpha_vs_spy` <= 0.0

Sub-branch D1:
- Convert signal to long-only (zero out all negative signals with `.clip(lower=0)`)
- Rationale: if the strategy is not generating alpha on shorts, removing them may improve vs benchmark
- Log action: "D1: Converted to long-only by clipping negative signals"

### Branch E: All Metrics Borderline (Sharpe 0.8–1.0, IC 0.01–0.03)
**Condition**: All metrics are close but not meeting thresholds

- Add a cross-sectional z-score normalization at the end:
  `signal = signal.groupby(level='date').transform(lambda x: (x - x.mean()) / x.std())`
- This improves signal quality by normalizing across the universe
- Log action: "E1: Added cross-sectional z-score normalization"

### Branch F: No Branch Matched (Catch-All)
**Condition**: None of Branches A–E conditions are satisfied

- Extend the lookback window by 1.5x (round to nearest integer).
- Log action: "F1: Catch-all — extended lookback as exploratory action"
- This ensures the loop always makes a change rather than stalling.

## After Applying Fix

1. Re-read `sandbox/factor.py` to confirm the change was applied correctly.
2. Confirm no new look-ahead bias was introduced.
3. Append the log action to "Refinement Actions Taken" in `sandbox/research_log.md`.
4. Do NOT apply more than one fix per iteration. One change at a time for interpretability.

## Output
Modified `sandbox/factor.py` with exactly one targeted change applied.
Write updated `sandbox/research_log.md` as the last action.
