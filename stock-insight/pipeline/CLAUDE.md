# Pipeline Directory Context

This directory contains the implementation of the stock report pipeline.

## Module Overview
- `generate_report.py` - Entry point with argparse and stdout contract
- `config.py` - Environment variables, TTLs, defaults, quota tracking
- `data/` - Data fetching (see `.claude/skills/stock-ingest/SKILL.md` for logic)
- `analyze/` - Metric computations (see `.claude/skills/stock-analyze/SKILL.md` for logic)
- `compile/` - Chart rendering (see `.claude/skills/stock-compile/SKILL.md` for logic)

## Execution
```bash
python pipeline/generate_report.py --ticker AAPL --mode beginner
```

## Output Contract
The script MUST print these lines at the end:
- `OUTPUT: output/{TICKER}_{DATE}.html`
- `QUALITY: price=OK|MISSING financials=OK|MISSING ...`
- `SECTIONS: overview,valuation,financials,...`
- `WARNINGS: ...` (if any)