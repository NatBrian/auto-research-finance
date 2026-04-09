"""Plotly chart generation for financial reports."""
import json
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


# Common layout settings for all charts
COMMON_LAYOUT = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "margin": dict(l=50, r=50, t=50, b=50),
    "font": dict(size=12),
    "autosize": True,
}

# Color scheme
COLORS = {
    "up": "#22c55e",      # Green
    "down": "#ef4444",    # Red
    "volume": "#93c5fd",  # Light blue
    "sma_20": "#3b82f6",  # Blue
    "sma_50": "#f97316",  # Orange
    "sma_200": "#a855f7", # Purple
    "revenue": "#60a5fa", # Blue
    "net_income": "#22c55e",  # Green
    "dividend": "#f59e0b",    # Amber
}


def create_price_chart(price_data: Optional[Dict], metrics: Optional[Dict] = None) -> Optional[Dict]:
    """Create candlestick chart with volume and SMAs."""
    if not price_data or not price_data.get("history"):
        return None

    try:
        history = price_data["history"]
        if isinstance(history, list):
            df = pd.DataFrame(history)
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], utc=True)
                df = df.set_index('Date')
        else:
            return None

        if df.empty:
            return None

        # Create subplots
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.7, 0.3],
            specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
        )

        # Candlestick
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name="OHLC",
                increasing_line_color=COLORS["up"],
                decreasing_line_color=COLORS["down"],
            ),
            row=1, col=1
        )

        # Add SMAs if metrics available
        if metrics:
            for period, color, name in [
                (20, COLORS["sma_20"], "SMA 20"),
                (50, COLORS["sma_50"], "SMA 50"),
                (200, COLORS["sma_200"], "SMA 200"),
            ]:
                key = f"sma_{period}"
                if metrics.get(key):
                    sma = df['Close'].rolling(window=period).mean()
                    fig.add_trace(
                        go.Scatter(
                            x=df.index,
                            y=sma,
                            name=name,
                            line=dict(color=color, width=1),
                            showlegend=True,
                        ),
                        row=1, col=1
                    )

        # Volume
        colors = [
            COLORS["up"] if df['Close'].iloc[i] >= df['Open'].iloc[i] else COLORS["down"]
            for i in range(len(df))
        ]
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df['Volume'],
                name="Volume",
                marker_color=colors,
                opacity=0.7,
            ),
            row=2, col=1
        )

        # Update layout
        fig.update_layout(
            **COMMON_LAYOUT,
            xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=500,
        )

        # Add range selector
        fig.update_xaxes(
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1M", step="month", stepmode="backward"),
                    dict(count=3, label="3M", step="month", stepmode="backward"),
                    dict(count=6, label="6M", step="month", stepmode="backward"),
                    dict(count=1, label="YTD", step="year", stepmode="todate"),
                    dict(count=1, label="1Y", step="year", stepmode="backward"),
                    dict(label="Max", step="all"),
                ]
            ),
            row=1, col=1
        )

        # Hide non-trading hours
        fig.update_xaxes(
            type="date",
            rangebreaks=[
                dict(bounds=["sat", "mon"]),
            ]
        )

        return {
            "json": fig.to_json(),
            "div": fig.to_html(full_html=False, include_plotlyjs=False),
        }

    except Exception as e:
        print(f"Price chart error: {e}", file=sys.stderr)
        return None


def create_technical_chart(price_data: Optional[Dict], metrics: Optional[Dict] = None) -> Optional[Dict]:
    """Create technical analysis chart with RSI and MACD (advanced mode only)."""
    if not price_data or not price_data.get("history"):
        return None

    try:
        history = price_data["history"]
        if isinstance(history, list):
            df = pd.DataFrame(history)
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], utc=True)
                df = df.set_index('Date')
        else:
            return None

        if len(df) < 26:  # Need at least 26 for MACD
            return None

        # Create subplots
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.05,
            row_heights=[0.5, 0.25, 0.25],
        )

        # Price with Bollinger Bands
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df['Close'],
                name="Price",
                line=dict(color="#60a5fa", width=1.5),
            ),
            row=1, col=1
        )

        # Calculate and add Bollinger Bands
        sma_20 = df['Close'].rolling(window=20).mean()
        std_20 = df['Close'].rolling(window=20).std()
        bb_upper = sma_20 + (2 * std_20)
        bb_lower = sma_20 - (2 * std_20)

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=bb_upper,
                name="BB Upper",
                line=dict(color="#9ca3af", width=1, dash="dash"),
                showlegend=False,
            ),
            row=1, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=bb_lower,
                name="BB Lower",
                line=dict(color="#9ca3af", width=1, dash="dash"),
                fill="tonexty",
                fillcolor="rgba(156, 163, 175, 0.1)",
                showlegend=False,
            ),
            row=1, col=1
        )

        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss.replace(0, float('nan'))
        rsi = 100 - (100 / (1 + rs))
        # Fill NaN with 50 (neutral) for display
        rsi = rsi.fillna(50)

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=rsi,
                name="RSI",
                line=dict(color="#8b5cf6", width=1.5),
            ),
            row=2, col=1
        )
        fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="#22c55e", row=2, col=1)

        # MACD
        ema_12 = df['Close'].ewm(span=12, adjust=False).mean()
        ema_26 = df['Close'].ewm(span=26, adjust=False).mean()
        macd = ema_12 - ema_26
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal

        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=macd,
                name="MACD",
                line=dict(color="#3b82f6", width=1.5),
            ),
            row=3, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=signal,
                name="Signal",
                line=dict(color="#f97316", width=1.5),
            ),
            row=3, col=1
        )

        # Update layout
        fig.update_layout(
            **COMMON_LAYOUT,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=600,
        )

        # RSI y-axis range
        fig.update_yaxes(range=[0, 100], row=2, col=1)

        return {
            "json": fig.to_json(),
            "div": fig.to_html(full_html=False, include_plotlyjs=False),
        }

    except Exception as e:
        print(f"Technical chart error: {e}", file=sys.stderr)
        return None


def create_revenue_chart(financials: Optional[Dict]) -> Optional[Dict]:
    """Create revenue and net income combo chart."""
    if not financials:
        return None

    try:
        income_stmt = financials.get("income_statement", [])
        if not income_stmt:
            return None

        # Prepare data - dates are now in rows, metrics are columns
        dates = []
        revenues = []
        net_incomes = []

        # Reverse to show oldest to newest
        for stmt in reversed(income_stmt[:8]):  # Last 8 quarters
            date = stmt.get("Date")
            revenue = stmt.get("Total Revenue")
            net_income = stmt.get("Net Income")

            if date and revenue:
                dates.append(str(date)[:10] if len(str(date)) > 10 else str(date))
                revenues.append(revenue / 1e9 if revenue else 0)  # Convert to billions
                net_incomes.append(net_income / 1e9 if net_income else 0)

        if not dates:
            return None

        # Create figure
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # Revenue bars
        fig.add_trace(
            go.Bar(
                x=dates,
                y=revenues,
                name="Revenue",
                marker_color=COLORS["revenue"],
                opacity=0.8,
            ),
            secondary_y=False,
        )

        # Net income line
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=net_incomes,
                name="Net Income",
                mode="lines+markers",
                line=dict(color=COLORS["net_income"], width=2),
                marker=dict(size=6),
            ),
            secondary_y=True,
        )

        # Update layout
        fig.update_layout(
            **COMMON_LAYOUT,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=350,
            xaxis_tickangle=-45,
        )

        fig.update_yaxes(title_text="Revenue (B)", secondary_y=False)
        fig.update_yaxes(title_text="Net Income (B)", secondary_y=True)

        return {
            "json": fig.to_json(),
            "div": fig.to_html(full_html=False, include_plotlyjs=False),
        }

    except Exception as e:
        print(f"Revenue chart error: {e}", file=sys.stderr)
        return None


def create_dividend_chart(dividends: Optional[Dict]) -> Optional[Dict]:
    """Create dividend history bar chart."""
    if not dividends or not dividends.get("history"):
        return None

    try:
        history = dividends["history"]

        # Group by year
        yearly_dividends = {}
        for div in history:
            date = div.get("date", "")
            year = date[:4] if date else "Unknown"
            amount = div.get("amount", 0)
            yearly_dividends[year] = yearly_dividends.get(year, 0) + amount

        if not yearly_dividends:
            return None

        years = sorted(yearly_dividends.keys())
        amounts = [yearly_dividends[y] for y in years]

        # Create bar chart
        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=years,
                y=amounts,
                name="Annual Dividend",
                marker_color=COLORS["dividend"],
                opacity=0.8,
            )
        )

        fig.update_layout(
            **COMMON_LAYOUT,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=300,
            xaxis_title="Year",
            yaxis_title="Dividend ($)",
        )

        return {
            "json": fig.to_json(),
            "div": fig.to_html(full_html=False, include_plotlyjs=False),
        }

    except Exception as e:
        print(f"Dividend chart error: {e}", file=sys.stderr)
        return None


def create_ownership_chart(ownership: Optional[Dict]) -> Optional[Dict]:
    """Create institutional ownership pie chart."""
    if not ownership or not ownership.get("holders"):
        return None

    try:
        holders = ownership["holders"][:10]  # Top 10

        names = []
        values = []

        for holder in holders:
            name = holder.get("Holder") or holder.get("holder", "Unknown")
            # Truncate long names for better display
            name = name[:25] + "..." if len(name) > 25 else name
            # Use pctHeld (percentage) for pie chart values, fallback to Shares
            value = holder.get("pctHeld") or holder.get("% Out") or holder.get("Shares") or holder.get("shares") or 0
            # If pctHeld is decimal (0.097), convert to percentage (9.7)
            if isinstance(value, (int, float)) and value < 1 and value > 0:
                value = value * 100
            names.append(name)
            values.append(value)

        if not names or sum(values) == 0:
            return None

        # Create pie chart
        fig = go.Figure()

        fig.add_trace(
            go.Pie(
                labels=names,
                values=values,
                hole=0.4,
                textinfo="percent",
                textposition="inside",
                insidetextorientation="radial",
                showlegend=True,
                legendgroup="holders",
            )
        )

        fig.update_layout(
            height=400,
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.02,
                font=dict(size=10),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=120, t=20, b=20),
        )

        return {
            "json": fig.to_json(),
            "div": fig.to_html(full_html=False, include_plotlyjs=False),
        }

    except Exception as e:
        print(f"Ownership chart error: {e}", file=sys.stderr)
        return None


def create_performance_chart(price_data: Optional[Dict]) -> Optional[Dict]:
    """Create performance bar chart (1D, 1W, 1M, 3M, 6M, 1Y, YTD)."""
    if not price_data or not price_data.get("history"):
        return None

    try:
        history = price_data["history"]
        if isinstance(history, list):
            df = pd.DataFrame(history)
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], utc=True)
                df = df.set_index('Date')
        else:
            return None

        if df.empty:
            return None

        current_price = df['Close'].iloc[-1]
        periods = {
            "1D": 1,
            "1W": 5,
            "1M": 22,
            "3M": 66,
            "6M": 132,
            "1Y": 252,
            "YTD": None,
        }

        labels = []
        changes = []
        colors = []

        for label, days in periods.items():
            if label == "YTD":
                # Find first trading day of year
                ytd_df = df[df.index.year == df.index[-1].year]
                if not ytd_df.empty:
                    start_price = ytd_df.iloc[0]['Close']
                else:
                    continue
            elif days:
                if len(df) >= days:
                    start_price = df['Close'].iloc[-days]
                else:
                    # Use oldest available data point
                    start_price = df['Close'].iloc[0]
            else:
                continue

            change = ((current_price - start_price) / start_price) * 100
            labels.append(label)
            changes.append(change)
            colors.append(COLORS["up"] if change >= 0 else COLORS["down"])

        if not labels:
            return None

        # Create horizontal bar chart
        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=changes,
                y=labels,
                orientation="h",
                marker_color=colors,
                text=[f"{c:+.1f}%" for c in changes],
                textposition="outside",
            )
        )

        fig.update_layout(
            **COMMON_LAYOUT,
            height=250,
            xaxis_title="Change (%)",
            showlegend=False,
        )

        # Add zero line
        fig.add_vline(x=0, line_dash="dash", line_color="gray", opacity=0.5)

        return {
            "json": fig.to_json(),
            "div": fig.to_html(full_html=False, include_plotlyjs=False),
        }

    except Exception as e:
        print(f"Performance chart error: {e}", file=sys.stderr)
        return None


def generate_charts(
    raw_data: Dict[str, Any],
    mode: str = "beginner"
) -> Tuple[Dict[str, Dict], List[str]]:
    """
    Generate all charts for the report.

    Returns: (charts_dict, warnings_list)
    """
    warnings = []
    charts = {}

    price_data = raw_data.get("price")
    financials = raw_data.get("financials")
    dividends = raw_data.get("dividends")
    ownership = raw_data.get("ownership")
    metrics = raw_data.get("metrics", {})

    # Price chart
    charts["price"] = create_price_chart(price_data, metrics)
    if not charts["price"]:
        warnings.append("Price chart generation failed")

    # Technical chart (advanced only)
    if mode == "advanced":
        charts["technical"] = create_technical_chart(price_data, metrics)
        if not charts["technical"]:
            warnings.append("Technical chart generation failed (insufficient data)")

    # Revenue chart
    charts["revenue"] = create_revenue_chart(financials)

    # Dividend chart
    charts["dividend"] = create_dividend_chart(dividends)

    # Ownership chart
    charts["ownership"] = create_ownership_chart(ownership)

    # Performance chart
    charts["performance"] = create_performance_chart(price_data)

    # Count generated charts
    generated = sum(1 for c in charts.values() if c is not None)

    print(f"COMPILE: charts_generated={generated} mode={mode}", file=sys.stderr)

    return charts, warnings