# Compile Module Context

Implements the stock-compile skill specification (see `.claude/skills/stock-compile/SKILL.md` for logic).

## Components
- `chart_renderer.py` - Plotly figure generators

## Chart Types
- Price Chart: Candlestick + Volume + SMAs
- Technical Chart (advanced): RSI + MACD + Bollinger
- Revenue Chart: Bar + Line combo
- Dividend Chart: Bar history
- Ownership Chart: Pie chart