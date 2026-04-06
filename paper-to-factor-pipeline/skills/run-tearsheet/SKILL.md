---
name: run-tearsheet
description: Execute the backtest and capture structured results. Use when the user says "run backtest", "run tearsheet", "backtest the factor", "execute tearsheet", or "check performance".
---

# Run Tearsheet Instructions

## Steps

1. Read `sandbox/research_log.md` first.
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
   ══════════════════════════════════════
   BACKTEST TEARSHEET — Iteration [N]
   ══════════════════════════════════════
   Signal Performance
     Sharpe Ratio:        [value]
     Information Coeff:   [value]
     Annualized Return:   [value]%
     Max Drawdown:        [value]%
     Turnover (daily):    [value]%

   vs. Benchmark (SPY Buy-and-Hold)
     Strategy Alpha:      [value]%
     SPY Sharpe:          [value]
     SPY Annual Return:   [value]%

   vs. ML Baselines
     XGBoost Sharpe:      [value]
     LogReg Sharpe:       [value]
     Strategy vs XGB:     [outperforms/underperforms]

   Data Integrity
     Universe Size:       [N] tickers
     Delisted Tickers:    [N] synthetic injections
     Train Period:        [start] to [end]
     Test Period:         [start] to [end]
   ══════════════════════════════════════
   ```

6. Append a new row to the "Performance History" table in `sandbox/research_log.md` with the current iteration's metrics.

7. Update "Last Backtest Result" in `sandbox/research_log.md` with the full JSON.

## Output
Write `sandbox/research_log.md` as the last action.
Return the parsed metrics dict to the orchestrator for decision logic.
