# Paper-to-Factor Pipeline

## Overview
Paper-to-Factor Pipeline is an autonomous quantitative research workflow for turning a topic into an implementable trading factor: it discovers relevant arXiv papers, translates paper logic into a `generate_signals` function, backtests with transaction costs and survivorship-aware data handling, compares against SPY and ML baselines, iteratively refines hypotheses, and exports a validated final factor module.

## Architecture Diagram
```text
+--------------------+
| User Input (Topic) |
+---------+----------+
          |
          v
+--------------------+
| Discovery          |
| (arXiv MCP tools)  |
+---------+----------+
          |
          v
+--------------------+
| Translation        |
| (paper -> factor)  |
+---------+----------+
          |
          v
+-------------------------------+
| Validation Loop               |
| backtest -> evaluate -> refine|
+---------+---------------------+
          |
          v
+--------------------+
| Finalization       |
| validated factor   |
+--------------------+
```

## Prerequisites
- Python 3.10+
- `venv` (standard Python virtual environment)
- Claude Code CLI installed

## Installation
1. Clone the repository and enter it:
   ```bash
   git clone <your-repo-url>
   cd paper-to-factor-pipeline
   ```
2. Create a virtual environment:
   ```bash
   python -m venv .venv
   ```
3. Activate the virtual environment:
   ```bash
   source .venv/bin/activate
   ```
   On Windows PowerShell:
   ```powershell
   .venv\Scripts\Activate.ps1
   ```
4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Starting MCP Servers
Run in two terminals from project root:

Terminal 1:
```bash
python mcp_servers/arxiv_server/server.py
```

Terminal 2:
```bash
python mcp_servers/backtest_server/server.py
```

## Running the Pipeline
```bash
claude run-skill paper-to-alpha --param topic="momentum strategies"
```

## Understanding the Output
The finalized strategy is written to `outputs/final_factor.py`. It contains a production-oriented `generate_signals(data)` implementation with a module docstring summarizing paper metadata and final validation metrics (Sharpe, IC, alpha vs SPY). You can import this file in other research/backtesting workflows and pass the same MultiIndex OHLCV schema used in this project.

## Configuration
`config/settings.yaml` controls data loading, execution assumptions, evaluation thresholds, and workflow paths.

| Key | Meaning |
|---|---|
| `data.start_date` | Historical data start date |
| `data.end_date` | Historical data end date |
| `data.train_ratio` | Fraction of dates used for model training |
| `data.validation_ratio` | Fraction of dates used for validation split |
| `data.test_ratio` | Fraction of dates used for test split |
| `data.universe_file` | CSV file containing historical universe membership |
| `data.manifest_file` | Data schema manifest path |
| `data.min_coverage_ratio` | Minimum acceptable ticker coverage before delisting injection |
| `execution.transaction_cost_bps` | Transaction cost in basis points applied in execution model |
| `execution.max_position_weight` | Max target position weight hint |
| `backtest.risk_free_rate` | Risk-free rate used in Sharpe computation |
| `backtest.periods_per_year` | Annualization factor (typically 252) |
| `thresholds.min_sharpe` | Minimum Sharpe threshold for finalization |
| `thresholds.min_ic` | Minimum information coefficient threshold |
| `thresholds.require_positive_alpha` | Require positive alpha versus SPY |
| `workflow.max_iterations` | Maximum refinement iterations |
| `workflow.research_log_path` | State file path used by skills |
| `workflow.factor_path` | Working factor file path |
| `workflow.output_path` | Final exported factor path |
| `logging.level` | Application logging level |

## Data Integrity Notes
The data loader explicitly mitigates survivorship bias by detecting missing/sparse ticker histories and injecting realistic delisting tails (NaNs after last valid trading date). For tickers with zero coverage, it creates a synthetic pre-delisting history then transitions to NaN. For partial coverage, it preserves all real observations and only fills post-last-real-date rows with NaN. A bounded 5-day forward-fill handles short operational gaps without hiding long absences.

## Limitations
- `yfinance` data quality/availability can vary across symbols and periods.
- arXiv retrieval is metadata/abstract-first unless downstream PDF parsing is added.
- Synthetic delisting tails are an approximation and not a substitute for full CRSP-grade survivorship datasets.
