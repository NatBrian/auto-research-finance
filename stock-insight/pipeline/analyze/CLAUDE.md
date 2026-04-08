# Analyze Module Context

Implements the stock-analyze skill specification (see `.claude/skills/stock-analyze/SKILL.md` for logic).

## Components
- `calculators.py` - Metric computations with validation

## Validation Thresholds
- RSI: ≥14 price rows
- Bollinger Bands: ≥30 rows
- SMA 200: ≥200 rows
- YoY Growth: ≥4 quarters