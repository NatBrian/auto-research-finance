# Paper-to-Factor Pipeline

An autonomous quantitative research workflow that turns a research topic into an implementable trading factor. It discovers relevant arXiv papers, translates paper logic into a `generate_signals` function, backtests with transaction costs and survivorship-aware data handling, compares performance against SPY and ML baselines, iteratively refines hypotheses, and exports a validated final factor module.

---

## 1. Overview

The workflow is designed to run inside Claude Code using Markdown skill files and MCP servers:

1. Discover relevant papers on arXiv for a user-supplied topic.
2. Let the user choose one paper from the ranked shortlist.
3. Translate the paper's mathematical signal into executable Python.
4. Backtest the generated factor on historical data with survivorship-aware handling.
5. Compare results against:
   - SPY buy-and-hold
   - XGBoost baseline
   - Logistic Regression baseline
6. Refine the hypothesis if validation thresholds are not met.
7. Export the validated result to `outputs/final_factor.py`.

The repo ships with a tracked placeholder `sandbox/factor.py` so the pipeline and tests have a stable working file before the translation step rewrites it.

---

## 2. Architecture

```text
┌──────────────────────────────────────────────────────────────┐
│ User Input                                                  │
│ topic="momentum strategies"                                 │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ Discovery                                                   │
│ MCP: arxiv_server                                           │
│ - search_papers()                                           │
│ - fetch_paper_details()                                     │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ Translation                                                 │
│ - read sandbox/research_log.md                              │
│ - read data/manifest.json                                   │
│ - write sandbox/factor.py                                   │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ Validation Loop                                             │
│ MCP: backtest_server                                        │
│ - load data                                                 │
│ - validate factor                                           │
│ - generate signals                                          │
│ - apply execution costs                                     │
│ - compare vs SPY and ML baselines                           │
└─────────────────────────────┬────────────────────────────────┘
                              │
                   criteria met? yes/no
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ Finalization                                                │
│ - strip debug prints                                        │
│ - add final module docstring                                │
│ - copy to outputs/final_factor.py                           │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | Required for pandas 2.x and type hints |
| `venv` | Standard library | Optional but recommended |
| Claude Code CLI | Current | Required for skill orchestration |
| Internet access | Required | Needed for arXiv and yfinance downloads |

---

## 4. Installation

```bash
cd paper-to-factor-pipeline

python -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
pip install -e .
```

---

## 5. Starting MCP Servers

Run these from the project root in separate terminals:

**Terminal 1**

```bash
python mcp_servers/arxiv_server/server.py
```

**Terminal 2**

```bash
python mcp_servers/backtest_server/server.py
```

Claude Code discovers the servers through `.claude.json`.

---

## 6. Running The Pipeline

```bash
claude run-skill paper-to-alpha --param topic="momentum strategies"
```

You can replace the topic with any research theme such as:

- `cross-sectional momentum`
- `mean reversion`
- `volatility risk premium`
- `pairs trading`

The discovery phase ranks candidate papers, presents the shortlist, and asks the user to choose one paper before the autonomous translation and validation loop begins.

---

## 7. Output

### `outputs/final_factor.py`

This is the final deliverable. It contains:

- a production-oriented `generate_signals(data)` implementation
- a module docstring with paper metadata
- the final validation summary metrics

### `sandbox/research_log.md`

This is the pipeline state file used by the skill workflow. It tracks:

- current phase and iteration
- selected paper metadata
- performance history
- last backtest result
- last error
- refinement actions taken
- final decision

---

## 8. Configuration

`config/settings.yaml` controls data loading, execution assumptions, validation thresholds, and workflow paths.

| Key | Meaning |
|---|---|
| `data.start_date` | Historical data start date |
| `data.end_date` | Historical data end date |
| `data.train_ratio` | Fraction of dates used for model training |
| `data.validation_ratio` | Fraction of dates used for validation split |
| `data.test_ratio` | Fraction of dates used for test split |
| `data.universe_file` | Historical universe membership CSV |
| `data.manifest_file` | Data schema manifest path |
| `data.min_coverage_ratio` | Minimum acceptable real-history coverage before delisting handling |
| `execution.transaction_cost_bps` | Transaction cost in basis points |
| `execution.max_position_weight` | Informational cap hint for generated factors |
| `backtest.risk_free_rate` | Risk-free rate used in Sharpe computation |
| `backtest.periods_per_year` | Annualization factor, typically `252` |
| `thresholds.min_sharpe` | Minimum Sharpe threshold |
| `thresholds.min_ic` | Minimum information coefficient threshold |
| `thresholds.require_positive_alpha` | Require positive alpha versus SPY |
| `workflow.max_iterations` | Maximum refinement iterations |
| `workflow.research_log_path` | Workflow state file |
| `workflow.factor_path` | Working factor path |
| `workflow.output_path` | Final exported factor path |

---

## 9. Data Integrity Notes

The loader is intentionally survivorship-aware:

- The active universe includes only tickers that were already in the universe at the chosen start date and not removed before that date.
- If a ticker has partial real history, the loader preserves observed data and injects `NaN` values after the last valid date to model delisting-style disappearance.
- If a ticker returns zero coverage despite being active at the start, the loader synthesizes a deterministic pre-delisting history and then transitions to `NaN`.
- When an actual `Date_Removed` exists in the universe file, that date is used to place the synthetic delisting tail when possible.
- Forward filling is capped at 5 business days so short operational gaps are tolerated without hiding long absences.

---

## 10. Benchmarks And Validation

The backtest loop reports:

- strategy Sharpe ratio
- information coefficient
- annualized return
- max drawdown
- daily turnover
- alpha versus SPY
- XGBoost Sharpe
- Logistic Regression Sharpe

Annualized returns are computed on a consistent simple-return basis across the strategy, SPY benchmark, and ML baseline outputs.

---

## 11. Limitations

- `yfinance` data quality and symbol coverage can vary.
- arXiv retrieval is metadata and abstract driven; PDF parsing is not included in this version.
- Synthetic delisting tails are a pragmatic approximation, not a CRSP-grade replacement.
- The included universe file is intentionally small and illustrative rather than a complete institutional research dataset.
