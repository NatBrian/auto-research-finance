---
name: paper-to-alpha
description: Main orchestrator for the Paper-to-Factor Pipeline. Use when the user says "run the pipeline", "start research", "paper to alpha", "run paper-to-factor", "research [topic]", or "execute the pipeline".
param: topic (string) - The research topic to investigate, e.g. "momentum strategies"
version: 2.0
---

# Paper-to-Alpha Orchestrator

You are executing the Paper-to-Factor Pipeline. Follow every step in order. Do not skip steps. Do not proceed past a PAUSE instruction without explicit user input.

## Pre-flight Check

1. Read `sandbox/research_log.md` first.
2. Read `config/settings.yaml` to load all configuration values.
3. Read `data/manifest.json` to understand the data schema.
4. Check if `sandbox/research_log.md` exists.
   - If it does NOT exist: Create it using the exact schema defined in Section 3 of the project documentation, setting phase to DISCOVERY, iteration to 0, status to IN_PROGRESS.
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
3. PAUSE: Present the top 5 paper results to the user. Ask them to select one by number. Wait for response.
4. Record the selected paper's arxiv_id, title, authors, abstract_summary, and key_formula in `sandbox/research_log.md` under "Selected Paper".
5. Update `phase` to TRANSLATION in `sandbox/research_log.md`.

## Phase: TRANSLATION

1. Read the file `.claude/skills/factor-translate/SKILL.md` using the Read tool.
2. Execute all instructions contained in that file.
3. Verify that `sandbox/factor.py` was written and contains a function named `generate_signals`.
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
2. Execute all instructions in that file, passing the current metrics and error as context.
3. Increment `iteration` by 1 in `sandbox/research_log.md`.
4. Return to entry of VALIDATION LOOP.

## Phase: FINALIZATION

1. Call `validate_factor('sandbox/factor.py')` logic (conceptually, or verify via `src/validator.py` execution if available) to check for look-ahead bias or syntax issues.
   - If `valid` is False: Log issues. Output a warning that the file has validation warnings. Proceed to copy, but prepend a `# WARNING: [issues]` block to the destination file.
2. Copy the contents of `sandbox/factor.py` to `outputs/final_factor.py`.
3. Remove all debug print statements from `outputs/final_factor.py` (stripping lines containing `print(` that are not in docstrings).
4. Add a module-level docstring to `outputs/final_factor.py` that includes: the source paper title, arxiv_id, final Sharpe ratio, final IC, and final alpha vs SPY.
5. Write final updates to `sandbox/research_log.md` as the last action.
6. Report success to user with full performance summary table from `sandbox/research_log.md`.
