---
name: generate-report
description: Generate comprehensive final report for the pipeline. Use when the user says "generate report", "create final report", "make the report", or when the pipeline completes successfully.
version: 1.0
---

# Generate Final Report Instructions

## Input

Read the following files to gather all necessary information:
1. `sandbox/research_log.md` - Paper metadata and pipeline execution log
2. `outputs/backtest_result.json` - Full backtest metrics (if exists)
3. `sandbox/factor.py` - Strategy implementation (to extract class name)

## Steps

### 1. Load Required Data

```python
import json
from pathlib import Path
from src.report_generator import generate_final_report

# Load backtest result
backtest_result_path = Path("outputs/backtest_result.json")
if backtest_result_path.exists():
    with open(backtest_result_path) as f:
        backtest_result = json.load(f)
else:
    # Run backtest first
    from src.core.backtester import EnhancedBacktester
    from src.utils import load_config
    config = load_config("config/settings.yaml")
    backtest_result = EnhancedBacktester(config).run()

# Extract strategy name from factor.py
factor_path = Path("sandbox/factor.py")
factor_content = factor_path.read_text()

# Find class name
import re
class_match = re.search(r'class\s+(\w+)\s*\(', factor_content)
strategy_name = class_match.group(1) if class_match else "Strategy"
```

### 2. Generate Report

```python
report_path = generate_final_report(
    research_log_path=Path("sandbox/research_log.md"),
    backtest_result=backtest_result,
    output_dir=Path("outputs"),
    strategy_name=strategy_name,
)

print(f"Report generated: {report_path}")
```

### 3. Verify Outputs

Confirm the following files were created:
- `outputs/FINAL_REPORT.md` - Comprehensive markdown report
- `outputs/backtest_charts.png` - Visualization charts
- `outputs/backtest_result.json` - Full metrics JSON

## Output

Report generation success message:

```
═════════════════════════════════════════════════════════════════
FINAL REPORT GENERATED
═════════════════════════════════════════════════════════════════

Report Location: outputs/FINAL_REPORT.md

Generated Files:
  - FINAL_REPORT.md     (Comprehensive markdown report)
  - backtest_charts.png (4-panel visualization)
  - backtest_result.json (Full metrics)

Report Sections:
  1. Executive Summary with paper information
  2. Paper Implementation Details
  3. Performance Metrics Comparison
  4. Backtest Visualizations
  5. Implementation Files & Quick Start
  6. Technical Notes & Limitations

View the report:
  cat outputs/FINAL_REPORT.md
═════════════════════════════════════════════════════════════════
```

## Error Handling

If matplotlib is not installed:
```
⚠️ matplotlib not installed. Install with:
    pip install matplotlib

Report will be generated without charts.
```

If backtest_result.json does not exist:
- Run the backtest first before generating the report
- Log warning and proceed with fresh backtest execution