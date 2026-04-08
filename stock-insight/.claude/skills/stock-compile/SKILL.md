---
name: stock-compile
description: Generate Plotly charts and render Jinja templates. Usage: /stock-compile <TICKER> [--mode beginner|advanced]
argument-hint: <TICKER> [--mode beginner|advanced]
disable-model-invocation: true
allowed-tools: Bash(python pipeline/compile/*) Read Write
---
# Charting & Rendering Skill

## Plotly Configuration (pipeline/compile/chart_renderer.py)

### Global Settings
```python
import plotly.graph_objects as go
import plotly.io as pio

# All figures use these defaults
pio.templates.default = "plotly_white"

COMMON_LAYOUT = dict(
    responsive=True,
    paper_bgcolor='rgba(0,0,0,0)',  # Transparent for dark mode
    plot_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=50, r=50, t=50, b=50),
    font=dict(size=12),
)
```

### Price Chart (Candlestick + Volume)
```python
def create_price_chart(df: pd.DataFrame) -> go.Figure:
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.7, 0.3]
    )

    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'],
        low=df['Low'], close=df['Close'], name='OHLC'
    ), row=1, col=1)

    # SMAs
    for period, color in [(20, 'blue'), (50, 'orange'), (200, 'purple')]:
        if f'SMA_{period}' in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index, y=df[f'SMA_{period}'],
                name=f'SMA {period}', line=dict(color=color, width=1)
            ), row=1, col=1)

    # Volume
    fig.add_trace(go.Bar(
        x=df.index, y=df['Volume'],
        name='Volume', marker_color='lightblue'
    ), row=2, col=1)

    # Rangeselector
    fig.update_xaxes(
        rangeselector=dict(
            buttons=[
                dict(count=1, label='1M', step='month', stepmode='backward'),
                dict(count=6, label='6M', step='month', stepmode='backward'),
                dict(count=1, label='YTD', step='year', stepmode='todate'),
                dict(count=1, label='1Y', step='year', stepmode='backward'),
                dict(label='Max', step='all')
            ]
        ),
        row=1, col=1
    )

    return fig
```

### Technical Chart (Advanced Only)
```python
def create_technical_chart(df: pd.DataFrame) -> go.Figure:
    """3 subplots: Price, RSI, MACD with shared x-axis."""
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.5, 0.25, 0.25]
    )

    # Price with Bollinger Bands
    fig.add_trace(go.Scatter(
        x=df.index, y=df['Close'], name='Price'
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['BB_Upper'], name='BB Upper',
        line=dict(dash='dash', color='gray')
    ), row=1, col=1)

    # RSI
    fig.add_trace(go.Scatter(
        x=df.index, y=df['RSI'], name='RSI'
    ), row=2, col=1)
    fig.add_hline(y=70, line_dash='dash', line_color='red', row=2, col=1)
    fig.add_hline(y=30, line_dash='dash', line_color='green', row=2, col=1)

    # MACD
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MACD'], name='MACD'
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df['MACD_Signal'], name='Signal'
    ), row=3, col=1)

    return fig
```

### Revenue Chart (Combo)
```python
def create_revenue_chart(df: pd.DataFrame) -> go.Figure:
    """Bar chart for Revenue, Line for Net Income."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Bar(
        x=df.index, y=df['Revenue'],
        name='Revenue', marker_color='lightblue'
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=df.index, y=df['Net Income'],
        name='Net Income', mode='lines+markers',
        line=dict(color='green', width=2)
    ), secondary_y=True)

    return fig
```

## Jinja2 Logic: Beginner vs Advanced

### Template Variables
```python
mode_context = {
    'beginner': {
        'label_style': 'expanded',  # "Price-to-Earnings Ratio"
        'tooltip': True,            # Show ℹ️ with explanation
        'table_rows': 5,            # Show only first 5 rows
        'technical_chart': False,   # Omit technical chart
    },
    'advanced': {
        'label_style': 'short',     # "P/E"
        'tooltip': False,           # No tooltips
        'table_rows': None,         # Show all rows with pagination
        'technical_chart': True,    # Include technical chart
    }
}
```

### Metric Labels
```python
METRIC_LABELS = {
    'pe_ratio': {
        'short': 'P/E',
        'expanded': 'Price-to-Earnings Ratio',
        'tooltip': 'Market price per dollar of earnings'
    },
    'pb_ratio': {
        'short': 'P/B',
        'expanded': 'Price-to-Book Ratio',
        'tooltip': 'Market price per dollar of book value'
    },
    # ... etc
}
```

## Mobile Table Rule (template/components/data_table.html.jinja2)
```html
<div class="overflow-x-auto max-w-full" style="-webkit-overflow-scrolling: touch;">
  <table class="w-full">
    <thead>
      <tr>
        {% for header in headers %}
        <th class="p-2 {% if loop.first %}sticky left-0 z-10 bg-white dark:bg-gray-800{% endif %}">
          {{ header }}
        </th>
        {% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for row in rows %}
      <tr>
        {% for cell in row %}
        <td class="p-2 {% if loop.first %}sticky left-0 z-10 bg-white dark:bg-gray-800{% endif %}">
          {{ cell }}
        </td>
        {% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
```

## Dark Mode Support
```javascript
// In report.html.jinja2 <head>
<script>
  tailwind.config = { darkMode: 'class' }

  // Initialize dark mode from localStorage
  if (localStorage.getItem('darkMode') === 'true') {
    document.documentElement.classList.add('dark');
  }

  function toggleDarkMode() {
    document.documentElement.classList.toggle('dark');
    localStorage.setItem('darkMode', document.documentElement.classList.contains('dark'));
  }
</script>
```

## Output Contract
```
COMPILE: ticker=$0 charts_generated=<count> mode=$mode output=output/{TICKER}_{DATE}.html
```

## Jinja2 Autoescape Note
```python
from jinja2 import Markup

# For Plotly JSON, prevent double-escaping
chart_json = Markup(fig.to_json())
```