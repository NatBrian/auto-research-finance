---
name: paper-to-alpha
description: Main orchestrator for the Paper-to-Factor Pipeline. Use when the user says "run the pipeline", "start research", "paper to alpha", "run paper-to-factor", "research [topic]", or "execute the pipeline".
param: topic (string) - The research topic to investigate, e.g. "momentum strategies"
version: 3.0
---

# Paper-to-Alpha Orchestrator (Hybrid Architecture)

You are executing the Paper-to-Factor Pipeline with support for both rule-based and ML-based strategies. Follow every step in order. Do not skip steps. Do not proceed past a PAUSE instruction without explicit user input.

## Pre-flight Check

1. Read `sandbox/research_log.md` first.
2. Read `config/settings.yaml` to load all configuration values.
3. Read `data/manifest.json` to understand the data schema.
4. Check if `sandbox/research_log.md` exists.
   - If it does NOT exist: Create it using the schema in `sandbox/research_log.md`, setting phase to DISCOVERY, iteration to 0, status to IN_PROGRESS.
   - If it DOES exist: Read it and resume from the current phase value.
5. Confirm both MCP servers are reachable by calling `ping_arxiv` and `ping_backtest`. If either fails, output the following message and HALT:
   ```
   ⚠️  MCP servers are not running. Please open two terminal windows and run:
       Terminal 1: python mcp_servers/arxiv_server/server.py
       Terminal 2: python mcp_servers/backtest_server/server.py
   Then re-run this skill.
   ```

## Phase: DISCOVERY

1. Read the file `.claude/skills/paper-discovery/SKILL.md` using the Read tool.
2. Execute all instructions contained in that file, passing the `topic` parameter.
3. **Detect Strategy Type**: Analyze the abstract of each paper to determine if it proposes:
   - **rule_based**: A formula-based signal (momentum, mean-reversion, RSI, etc.)
   - **ml_based**: A machine learning model (neural network, random forest, etc.)
   - **statistical**: A statistical model (ARIMA, GARCH, cointegration, etc.)
4. PAUSE: Present the top 5 paper results to the user with their detected types. Ask them to select one by number. Wait for response.
5. Record the selected paper's metadata in `sandbox/research_log.md` under "Selected Paper".
6. Set `strategy_type` in research_log to the detected type.
7. Update `phase` to TRANSLATION in `sandbox/research_log.md`.

## Phase: TRANSLATION

1. Read the file `.claude/skills/factor-translate/SKILL.md` using the Read tool.
2. Execute all instructions contained in that file, passing the `strategy_type` parameter.
3. Verify that `sandbox/factor.py` was written correctly:
   - For **rule_based**: Contains `generate_signals(data)` function or `RuleBasedStrategy` subclass
   - For **ml_based**: Contains `MLStrategy` subclass with `fit()` and `generate_signals()` methods
   - For **statistical**: Contains `StatisticalStrategy` subclass
4. Update `phase` based on strategy type:
   - If `strategy_type` == "ml_based": Set phase to **TRAINING**
   - Otherwise: Set phase to **VALIDATION**

## Phase: TRAINING (ML-based strategies only)

This phase is skipped for rule-based strategies.

1. Read the file `.claude/skills/model-train/SKILL.md` using the Read tool.
2. Execute all instructions to train the ML model:
   - Load training data
   - Configure features from `config/settings.yaml` ml.default_features
   - Train model with optional hyperparameter tuning
   - Save model to `sandbox/models/trained_model.pkl`
3. Update `sandbox/research_log.md`:
   - Set `is_fitted` to true
   - Record `hyperparameters` used
   - Record `feature_set` used
   - Record `feature_importance` from trained model
4. Update `phase` to VALIDATION in `sandbox/research_log.md`.

## Phase: VALIDATION LOOP

Execute the following loop. Read the current `iteration` and `max_iterations` from `sandbox/research_log.md` before each iteration.

### Entry check:
- If `iteration` >= `max_iterations`:
  - Update `phase` to FAILED and `status` to COMPLETE in `sandbox/research_log.md`.
  - Update "Final Decision" `outcome` to FAILED, `reason` to "Max iterations reached without meeting criteria".
  - Report failure to user with the full Performance History table.
  - Write updated `sandbox/research_log.md` and HALT.

### Validation step:
1. Read the file `.claude/skills/run-tearsheet/SKILL.md` using the Read tool.
2. Execute all instructions in that file.
3. Parse the JSON result from the backtest. Update "Last Backtest Result" in `sandbox/research_log.md`.

### Error check:
- If the result contains `"status": "error"`:
  - Update "Last Error" in `sandbox/research_log.md` with the error message.
  - Proceed to REFINEMENT phase.

### Success criteria check (ALL must be true):
- `sharpe_ratio` > 0.7
- `information_coefficient` > 0.02
- `alpha_vs_spy` > 0.0 (strategy beats SPY on annualized alpha)

If ALL criteria are met:
- Update `phase` to FINALIZED in `sandbox/research_log.md`.
- Update "Final Decision" accordingly.
- Proceed to FINALIZATION.

If criteria are NOT met:
- Proceed to REFINEMENT.

### Refinement step:
1. Read the file `.claude/skills/hypothesis-refine/SKILL.md` using the Read tool.
2. Execute all instructions in that file, passing:
   - Current metrics
   - Error (if any)
   - Strategy type (for type-specific refinement actions)
3. Increment `iteration` by 1 in `sandbox/research_log.md`.
4. Return to entry of VALIDATION LOOP.

## Phase: FINALIZATION

1. Validate the final factor/strategy using `src/validator.py` logic.
   - If `valid` is False: Log issues. Output a warning that the file has validation warnings.
2. Copy the contents of `sandbox/factor.py` to `outputs/final_factor.py`.
3. If `strategy_type` == "ml_based":
   - Copy `sandbox/models/trained_model.pkl` to `outputs/final_model.pkl`
   - Include model metadata in the output
4. Remove all debug print statements from `outputs/final_factor.py`.
5. Add a module-level docstring to `outputs/final_factor.py` that includes:
   - Source paper title and arxiv_id
   - Strategy type
   - Final metrics: Sharpe, Sortino, Calmar, IC, Alpha vs SPY
   - For ML: Feature importance ranking
6. Write final updates to `sandbox/research_log.md` as the last action.
7. **Generate Final Report**: Run the report generator script:
   ```python
   from src.report_generator import generate_final_report
   from pathlib import Path
   import json

   # Load backtest result
   with open("outputs/backtest_result.json") as f:
       backtest_result = json.load(f)

   # Get strategy name from research_log
   strategy_name = "Strategy"  # Extract from factor.py class name

   # Generate comprehensive report
   report_path = generate_final_report(
       research_log_path=Path("sandbox/research_log.md"),
       backtest_result=backtest_result,
       output_dir=Path("outputs"),
       strategy_name=strategy_name,
   )
   ```
8. Report success to user with:
   - Full performance summary table
   - Feature importance (if ML)
   - Sector exposure summary
   - Comparison vs XGBoost and Logistic Regression baselines
   - **Path to the final report**: `outputs/FINAL_REPORT.md`