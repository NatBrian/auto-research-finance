---
name: run-tearsheet
description: Execute the backtest and capture structured results. Use when the user says "run backtest", "run tearsheet", "backtest the factor", "execute tearsheet", or "check performance".
version: 3.0
---

# Run Tearsheet Instructions (Enhanced Metrics)

## Steps

1. Read `sandbox/research_log.md` first to get:
   - Current iteration number
   - Strategy type
   - Whether model is fitted (for ML strategies)

2. Call the MCP tool `run_backtest` with no arguments.
   The tool handles all internal configuration via `config/settings.yaml`.

3. The tool returns a JSON string. Parse it.

4. If `status` is `"error"`:
   - Log the full `message` field to "Last Error" in `sandbox/research_log.md`
   - Log the full result JSON to "Last Backtest Result" in `sandbox/research_log.md`
   - Write updates to `sandbox/research_log.md` as the last action
   - Return control to orchestrator with error status

5. If `status` is `"success"`, extract and display a formatted tearsheet:

   ```
   ═════════════════════════════════════════════════════════════════
   BACKTEST TEARSHEET — Iteration [N]
   ═════════════════════════════════════════════════════════════════

   Strategy: [strategy_type] | Fitted: [is_fitted]

   ─────────────────────────────────────────────────────────────────
   RISK-ADJUSTED PERFORMANCE
   ─────────────────────────────────────────────────────────────────
     Sharpe Ratio:          [value]
     Sortino Ratio:         [value]    (downside risk only)
     Calmar Ratio:          [value]    (return / max drawdown)
     Information Coeff:     [value]
     Hit Rate:              [value]%   (correct direction)
     Profit Factor:         [value]    (gross profit / gross loss)

   ─────────────────────────────────────────────────────────────────
   RETURNS & RISK
   ─────────────────────────────────────────────────────────────────
     Annualized Return:     [value]%
     Max Drawdown:          [value]%
     Daily Turnover:        [value]%

   ─────────────────────────────────────────────────────────────────
   vs. BENCHMARK (SPY Buy-and-Hold)
   ─────────────────────────────────────────────────────────────────
     Strategy Alpha:        [value]%
     Beta to SPY:           [value]
     SPY Sharpe:            [value]
     SPY Annual Return:     [value]%

   ─────────────────────────────────────────────────────────────────
   vs. ML BASELINES
   ─────────────────────────────────────────────────────────────────
     XGBoost Sharpe:        [value]
     LogisticReg Sharpe:    [value]
     Strategy vs Best ML:   [outperforms/underperforms]

   ─────────────────────────────────────────────────────────────────
   SECTOR EXPOSURE
   ─────────────────────────────────────────────────────────────────
     Top Sector:            [sector] ([weight]%)
     Sector Concentration:  [herfindahl]
     Sectors: [list top 3-5]

   ─────────────────────────────────────────────────────────────────
   FEATURE IMPORTANCE (ML only)
   ─────────────────────────────────────────────────────────────────
     1. [feature_1]: [importance]
     2. [feature_2]: [importance]
     3. [feature_3]: [importance]
     ...

   ─────────────────────────────────────────────────────────────────
   DATA INTEGRITY
   ─────────────────────────────────────────────────────────────────
     Universe Size:         [N] tickers
     Delisted Tickers:      [N] synthetic injections
     Train Period:          [start] to [end]
     Val Period:            [start] to [end]
     Test Period:           [start] to [end]
   ═════════════════════════════════════════════════════════════════
   ```

6. Update `sandbox/research_log.md`:

   a. Append a new row to "Performance History" table:
   ```
   | [N] | [Sharpe] | [Sortino] | [Calmar] | [IC] | [Turnover] | [Alpha] | [Beta] | [vs_XGB] | [vs_LR] | [Error] |
   ```

   b. Update "Last Backtest Result" with the full JSON.

   c. Update "Sector Exposure" table with current sector weights.

   d. Update "Feature Importance" JSON block (for ML strategies).

7. Compare against thresholds from `config/settings.yaml`:
   - `thresholds.min_sharpe`
   - `thresholds.min_ic`
   - `thresholds.min_sortino`
   - `thresholds.max_beta`

## Output
Write `sandbox/research_log.md` as the last action.
Return the parsed metrics dict to the orchestrator for decision logic.