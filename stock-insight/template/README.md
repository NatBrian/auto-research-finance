# Professional Financial Report Template

A modern, single-page Jinja2 template system for generating professional stock financial reports, inspired by sectors.app design principles.

## Features

- **Modern Dark Theme**: Professional dark mode with cyan/teal accent colors
- **Single-Page Layout**: Comprehensive report without tabs - ideal for PDF export
- **Responsive Design**: Mobile-friendly with proper breakpoints
- **Plotly.js Charts**: Client-side rendered interactive charts
- **Print-Ready**: Optimized for PDF export with clean print styles
- **All Jinja2 Variables Preserved**: 100% compatible with existing data structures

## File Structure

```
financial_report_template/
├── report.html.jinja2          # Main single-page template (USE THIS)
├── components/
│   ├── metric_card.html.jinja2 # Reusable metric card component
│   ├── data_table.html.jinja2  # Reusable data table component
│   └── chart_container.html.jinja2 # Reusable chart container component
├── sections/
│   ├── price_metrics.html.jinja2   # Price & market data section
│   ├── financials.html.jinja2      # Financial statements section
│   ├── dividends.html.jinja2       # Dividend information section
│   ├── analyst.html.jinja2         # Analyst coverage section
│   ├── ownership.html.jinja2       # Institutional ownership section
│   └── news.html.jinja2            # News section
└── README.md
```

## Usage

### Main Template

Simply use `report.html.jinja2` as your main template. It includes all sections in a single comprehensive page.

```python
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('financial_report_template'))
template = env.get_template('report.html.jinja2')

html = template.render(
    ticker="AAPL",
    date="2026-04-08",
    mode="advanced",
    sections=["overview", "financials", "valuation", "dividends", "analyst", "ownership", "news"],
    is_beginner=False,
    is_advanced=True,
    profile=profile_data,
    price=price_data,
    financials=financials_data,
    dividends=dividends_data,
    analyst=analyst_data,
    ownership=ownership_data,
    news=news_data,
    metrics=metrics_data,
    charts=charts_data
)
```

### Using Section Templates (Optional)

If you prefer modular templates, you can include individual sections:

```jinja2
{% include 'sections/price_metrics.html.jinja2' %}
{% include 'sections/financials.html.jinja2' %}
{% include 'sections/dividends.html.jinja2' %}
{% include 'sections/analyst.html.jinja2' %}
{% include 'sections/ownership.html.jinja2' %}
{% include 'sections/news.html.jinja2' %}
```

## Data Variables

All original Jinja2 variables are preserved exactly:

### Template Data
- `ticker`: str (e.g., "AAPL")
- `date`: str (e.g., "2026-04-08")
- `mode`: "beginner" or "advanced"
- `sections`: list of active tabs
- `is_beginner`: bool
- `is_advanced`: bool

### Profile Dict
- `profile.name`, `profile.sector`, `profile.industry`, `profile.country`
- `profile.exchange`, `profile.website`, `profile.employees`, `profile.description`

### Price Dict
- `price.current_price`, `price.change`, `price.change_pct`
- `price.volume`, `price.avg_volume`, `price.market_cap`
- `price.high_52w`, `price.low_52w`, `price.open`, `price.high`, `price.low`

### Financials Dict
- `financials.income_statement`: list of {Date, Total Revenue, Net Income, ...}
- `financials.balance_sheet`: list of {Date, Total Assets, Total Equity, ...}
- `financials.cashflow`: list of {Date, Operating Cash Flow, ...}
- `financials.info.total_revenue`, `.net_income`, `.total_assets`, `.total_equity`, `.total_debt`, `.ebitda`

### Dividends Dict
- `dividends.history`: list of {date, amount}
- `dividends.ttm_dividend`, `dividends.total_dividends`

### Analyst Dict
- `analyst.grades`: {buy: int, hold: int, sell: int}
- `analyst.price_target`: {mean, median, high, low}
- `analyst.history`: list of recommendation periods

### Ownership Dict
- `ownership.holders`: list of {Holder, Shares, pctHeld, ...}
- `ownership.total_institutions`: int

### News List
- `news[].title`, `.publisher`, `.link`, `.published`, `.summary`

### Metrics Dict
- `metrics.pe_ratio.value`, `metrics.pb_ratio.value`, `metrics.ps_ratio.value`
- `metrics.pcf_ratio.value`, `metrics.peg_ratio.value`, `metrics.ev_ebitda.value`
- `metrics.roe.value`, `metrics.roa.value`, `metrics.net_margin.value`
- `metrics.debt_equity.value`, `metrics.debt_assets.value`
- `metrics.dividend_yield.value`, `metrics.dividend_cagr_5y.value`
- `metrics.revenue_yoy.value`, `metrics.net_income_yoy.value`
- `metrics.sma_20.value`, `metrics.sma_50.value`, `metrics.sma_200.value`
- `metrics.rsi.value`, `metrics.macd.value`, `metrics.macd_signal.value`
- `metrics.bb_upper.value`, `metrics.bb_middle.value`, `metrics.bb_lower.value`

### Charts Dict (Plotly JSON)
Render with `Plotly.newPlot(divId, {{ charts.*.json|safe }})`
- `charts.price.json` → div id="price-chart"
- `charts.technical.json` → div id="technical-chart" (advanced only)
- `charts.revenue.json` → div id="revenue-chart"
- `charts.dividend.json` → div id="dividend-chart"
- `charts.ownership.json` → div id="ownership-chart"
- `charts.performance.json` → div id="performance-chart"

## Design System

### Colors
- **Background**: `#0f172a` (dark slate)
- **Card Background**: `#1e293b` (slate-800)
- **Accent (Brand)**: `#06b6d4` (cyan-500)
- **Positive/Up**: `#10b981` (emerald-500)
- **Negative/Down**: `#ef4444` (red-500)

### Typography
- **Font Family**: Inter (Google Fonts)
- **Headings**: Bold, tracked tight
- **Numbers**: Bold, larger sizes
- **Labels**: Uppercase, tracked wide, muted color

### Components
- **Cards**: Rounded corners (12px), subtle borders, hover effects
- **Metric Cards**: Large numbers with small labels
- **Tables**: Clean, minimal, with sticky first column
- **Charts**: Transparent background, themed axes

## PDF Export

The template is optimized for PDF export:

1. Click the "Export PDF" button in the header
2. Use browser's print dialog (Ctrl/Cmd + P)
3. Select "Save as PDF"
4. Print styles automatically apply for clean output

## Customization

### Dark Mode Toggle

To add a dark mode toggle, add this button to the header:

```html
<button onclick="toggleDarkMode()" class="...">
    <!-- Sun/Moon icons -->
</button>
```

### Custom Colors

Modify the Tailwind config in the template:

```javascript
tailwind.config = {
    theme: {
        extend: {
            colors: {
                brand: {
                    // Your custom brand colors
                }
            }
        }
    }
}
```

## Dependencies

- **Tailwind CSS** (CDN): Styling framework
- **Plotly.js** (CDN): Chart rendering
- **Inter Font** (Google Fonts): Typography

## Browser Support

- Chrome 80+
- Firefox 75+
- Safari 13+
- Edge 80+

## License

MIT License - Free for personal and commercial use.
