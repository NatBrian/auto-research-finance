---
name: factor-translate
description: Translate a selected paper's signal into executable Python code. Use when the user says "translate the paper", "write the factor", "convert signal to code", "implement the formula", or "generate factor code".
---

# Factor Translation Instructions

## Input
Read `sandbox/research_log.md` first to get the selected paper's arxiv_id, title, abstract_summary, and key_formula.
Read `data/manifest.json` to understand the exact column names and index structure available.

## Steps

1. Analyze the paper's key_formula and abstract_summary. Identify:
   - The type of signal (cross-sectional rank, time-series momentum, mean-reversion, volatility, etc.)
   - The required lookback window(s)
   - Any required transformations (log returns, z-score, rolling std, etc.)
   - Whether it is a long-only, long-short, or dollar-neutral strategy

2. Write `sandbox/factor.py` with the following exact structure:

```python
"""
Factor: [Paper Title]
ArXiv ID: [arxiv_id]
Signal Type: [signal type]
Lookback: [lookback period in days]
"""

import pandas as pd
import numpy as np


def generate_signals(data: pd.DataFrame) -> pd.Series:
    """
    Generate trading signals from market data.

    Args:
        data: MultiIndex DataFrame with index levels (date, ticker).
              Columns: Open, High, Low, Close, Volume (per manifest.json).
              All values are point-in-time — no future data leaks in.

    Returns:
        pd.Series with the same MultiIndex (date, ticker).
        Values are signal strengths (floats, not restricted to -1/0/1).
        Higher values = stronger long signal.
        NaN = no position for that ticker on that date.

    Raises:
        ValueError: If required columns are missing from data.
    """
    # --- Input validation ---
    required_cols = ["Open", "High", "Low", "Close", "Volume"]
    missing = [c for c in required_cols if c not in data.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # --- Signal computation ---
    # Critical rules:
    # 1. Use .shift(1) before any signal computation to avoid look-ahead bias
    # 2. Use groupby(level='ticker') for any ticker-level operations
    # 3. Cross-sectional rank at the end: signal.groupby(level='date').rank(pct=True)
    # 4. Fill NaN from insufficient history with np.nan, not 0
    # 5. Do NOT use any data after the current row

    signals = pd.Series(np.nan, index=data.index, name="signal")

    # [AGENT WRITES IMPLEMENTATION HERE]

    return signals
```

3. After writing `sandbox/factor.py`, perform a self-review:
   - Confirm no use of `.shift(-1)` or any negative shift (look-ahead)
   - Confirm the return type is pd.Series with correct MultiIndex
   - Confirm NaN handling is explicit
   - Confirm the function does not import or read any external files

4. If any self-review check fails, fix the code before proceeding.

## Output
Write final status updates to `sandbox/research_log.md` as the last action.
`sandbox/factor.py` must exist and be importable.
