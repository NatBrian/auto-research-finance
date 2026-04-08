---
name: stock-analyze
description: Compute financial metrics with validation rules. Usage: /stock-analyze <TICKER> [--mode beginner|advanced]
argument-hint: <TICKER> [--mode beginner|advanced]
disable-model-invocation: true
allowed-tools: Bash(python pipeline/analyze/*) Read
---
# Metric Computation Skill

## Validation Thresholds (skip if insufficient data)
- RSI: require ≥14 price rows
- Bollinger Bands: ≥30 rows
- SMA 200: ≥200 rows
- YoY Growth: require ≥2 full fiscal periods (4 quarters)

## Formulas (implement exactly in pipeline/analyze/calculators.py)

### Profitability Ratios
```python
ROE = Net Income / Total Equity
ROA = Net Income / Total Assets
Net Margin = Net Income / Total Revenue
Gross Margin = Gross Profit / Total Revenue
Operating Margin = Operating Income / Total Revenue
```

### Leverage Ratios
```python
Debt_to_Equity = Total Debt / Total Equity
Debt_to_Assets = Total Debt / Total Assets
Interest_Coverage = EBIT / Interest Expense
```

### Valuation Ratios
```python
P_E = Market Cap / Net Income
P_B = Market Cap / Total Equity
P_S = Market Cap / Total Revenue
P_CF = Market Cap / Operating Cash Flow  # Fallback if P/E missing
PEG = P_E / Earnings Growth Rate
```

### Dividend Metrics
```python
Dividend_Yield_TTM = (Sum of dividends last 12mo / Current Price) * 100
Payout_Ratio = Total Dividends / Net Income
Dividend_Growth_5Y = CAGR of dividends over 5 years
```

### Growth Metrics
```python
YoY_Revenue_Growth = ((Current Revenue - Revenue_4Q_ago) / Revenue_4Q_ago) * 100
YoY_Earnings_Growth = ((Current EPS - EPS_4Q_ago) / EPS_4Q_ago) * 100
CAGR = (Ending Value / Beginning Value) ** (1/n) - 1
```

### Technical Indicators
```python
RSI_14 = 100 - (100 / (1 + RS))  # RS = Avg Gain / Avg Loss
SMA_20 = Price.rolling(20).mean()
SMA_50 = Price.rolling(50).mean()
SMA_200 = Price.rolling(200).mean()
MACD = EMA_12 - EMA_26
MACD_Signal = MACD.ewm(span=9).mean()
Bollinger_Upper = SMA_20 + (2 * StdDev_20)
Bollinger_Lower = SMA_20 - (2 * StdDev_20)
```

## Edge Cases
- Denominator zero/negative → return None (do not crash)
- Round percentages to 1 decimal
- Round currency to 2 decimals
- Use pandas-ta for technical indicators; fallback to manual if unavailable

## Mode Differences
### Beginner Mode
- Basic metrics only (P/E, P/B, ROE, ROA, Net Margin)
- No technical indicators
- Simplified labels with tooltips

### Advanced Mode
- All metrics including leverage ratios
- Full technical analysis (RSI, MACD, Bollinger)
- Detailed financial breakdowns

## Output Contract
```
ANALYZE: ticker=$0 metrics_computed=<count> skipped=<list> mode=$mode
WARNINGS: <semicolon-separated list of validation skips>
```

## Implementation Notes
```python
import pandas_ta as ta

def compute_rsi(prices: pd.Series, period: int = 14) -> float:
    """Compute RSI with validation."""
    if len(prices) < period:
        return None
    rsi = ta.rsi(prices, length=period)
    return round(rsi.iloc[-1], 1) if not pd.isna(rsi.iloc[-1]) else None

def safe_divide(numerator, denominator):
    """Safe division that returns None for invalid denominators."""
    if denominator is None or denominator == 0:
        return None
    try:
        result = numerator / denominator
        return round(result, 4) if abs(result) < 1000000 else None
    except (TypeError, ZeroDivisionError):
        return None
```