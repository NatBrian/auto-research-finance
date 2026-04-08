---
name: stock-report
description: Generate interactive HTML financial report for a stock ticker. Orchestrates stock-ingest, stock-analyze, and stock-compile skills. Usage: /stock-report <TICKER> [beginner|advanced]
argument-hint: <TICKER> [beginner|advanced]
disable-model-invocation: true
allowed-tools: Bash(python pipeline/*) Read Write
---
# Report Orchestrator Skill

## Invocation
User runs: `/stock-report $0 $1` where:
- `$0` = ticker symbol (required, e.g., AAPL, BBCA.JK)
- `$1` = mode (optional: beginner|advanced, default: beginner)

## Execution Sequence
1. Validate ticker: alphanumeric + optional `.JK`/`.US` suffix
2. Invoke stock-ingest skill: `/stock-ingest $0` → wait for completion
3. Invoke stock-analyze skill: `/stock-analyze $0 --mode ${1:-beginner}` → wait for completion
4. Invoke stock-compile skill: `/stock-compile $0 --mode ${1:-beginner}` → wait for completion
5. Run pipeline: `python pipeline/generate_report.py --ticker $0 --mode ${1:-beginner}`
6. Parse stdout contract:
   - `OUTPUT: <path>` → open and present HTML file
   - `CRITICAL: <reason>` → inform user of failure + reason
   - `WARNINGS: <list>` → relay after success
   - `QUALITY: <key=value>` → summarize data coverage
7. If stdout lacks contract lines, find most recent `output/{TICKER}_*.html` and present it.

## Error Handling
- Permission denied: instruct user to approve Bash commands in `.claude/settings.json`
- Import error: run `pip install -r requirements.txt` then retry
- API quota: suggest waiting for TTL or switching fallback per stock-ingest skill spec
- Skill invocation failure: read target skill's SKILL.md, fix, retry

## Ticker Validation
```python
import re
pattern = r'^[A-Z]{1,5}(\.(JK|US))?$'
# Valid: AAPL, BBCA.JK, MSFT.US, GOOGL
# Invalid: apple, AAPL123, BBCA.JK.US
```

## Success Criteria
- Output HTML file exists and is non-empty
- File contains valid HTML structure (<!DOCTYPE html>)
- File size > 10KB (indicates data was rendered)