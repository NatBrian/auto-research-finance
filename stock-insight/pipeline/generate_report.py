#!/usr/bin/env python3
"""Generate interactive HTML financial report for a stock ticker."""
import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

from pipeline.config import (
    OUTPUT_DIR, TEMPLATE_DIR, CACHE_DB, REPORT_SECTIONS, CONDITIONAL_SECTIONS
)
from pipeline.data.fetchers import fetch_all_data
from pipeline.data.db import init_db
from pipeline.analyze.calculators import compute_all_metrics
from pipeline.compile.chart_renderer import generate_charts


def validate_ticker(ticker: str) -> bool:
    """Validate ticker format: alphanumeric + optional .JK/.US suffix."""
    pattern = r'^[A-Z]{1,5}(\.(JK|US))?$'
    return bool(re.match(pattern, ticker.upper()))


def format_large_number(value: float) -> str:
    """Format large numbers with K/M/B/T suffixes."""
    if value is None:
        return "N/A"
    abs_val = abs(value)
    if abs_val >= 1e12:
        return f"${value/1e12:.2f}T"
    elif abs_val >= 1e9:
        return f"${value/1e9:.2f}B"
    elif abs_val >= 1e6:
        return f"${value/1e6:.2f}M"
    elif abs_val >= 1e3:
        return f"${value/1e3:.2f}K"
    return f"${value:.2f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format as percentage with sign for changes."""
    if value is None:
        return "N/A"
    return f"{value:.{decimals}f}%"


def get_metric_label(metric_key: str, mode: str) -> Dict[str, str]:
    """Get metric label based on mode (beginner/advanced)."""
    labels = {
        'pe_ratio': {'short': 'P/E', 'expanded': 'Price-to-Earnings', 'tooltip': 'Stock price divided by earnings per share'},
        'pb_ratio': {'short': 'P/B', 'expanded': 'Price-to-Book', 'tooltip': 'Stock price divided by book value per share'},
        'ps_ratio': {'short': 'P/S', 'expanded': 'Price-to-Sales', 'tooltip': 'Stock price divided by revenue per share'},
        'pcf_ratio': {'short': 'P/CF', 'expanded': 'Price-to-Cash Flow', 'tooltip': 'Stock price divided by cash flow per share'},
        'roe': {'short': 'ROE', 'expanded': 'Return on Equity', 'tooltip': 'Net income as percentage of shareholder equity'},
        'roa': {'short': 'ROA', 'expanded': 'Return on Assets', 'tooltip': 'Net income as percentage of total assets'},
        'net_margin': {'short': 'Net Margin', 'expanded': 'Net Profit Margin', 'tooltip': 'Net income as percentage of revenue'},
        'debt_equity': {'short': 'D/E', 'expanded': 'Debt-to-Equity', 'tooltip': 'Total debt divided by shareholder equity'},
        'dividend_yield': {'short': 'Div Yield', 'expanded': 'Dividend Yield', 'tooltip': 'Annual dividends as percentage of stock price'},
    }
    label_info = labels.get(metric_key, {'short': metric_key, 'expanded': metric_key, 'tooltip': ''})
    return {
        'short': label_info['short'],
        'expanded': label_info['expanded'],
        'tooltip': label_info['tooltip'],
        'display': label_info['expanded'] if mode == 'beginner' else label_info['short']
    }


def prepare_template_data(
    ticker: str,
    raw_data: Dict[str, Any],
    metrics: Dict[str, Any],
    charts: Dict[str, Any],
    mode: str
) -> Dict[str, Any]:
    """Prepare all data for Jinja2 template rendering."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Determine which sections to show
    active_sections = []
    for section in REPORT_SECTIONS:
        if section in CONDITIONAL_SECTIONS:
            # Check if data exists for conditional sections
            if section == "analyst" and raw_data.get("analyst"):
                active_sections.append(section)
            elif section == "dividends" and raw_data.get("dividends"):
                active_sections.append(section)
            elif section == "ownership" and raw_data.get("ownership"):
                active_sections.append(section)
            elif section == "news" and raw_data.get("news"):
                active_sections.append(section)
        else:
            active_sections.append(section)

    # Prepare price data
    price_info = raw_data.get("price", {})
    profile = raw_data.get("profile", {})

    # Format metrics with labels
    formatted_metrics = {}
    for key, value in metrics.items():
        formatted_metrics[key] = {
            'value': value,
            'label': get_metric_label(key, mode),
            'formatted': format_large_number(value) if 'ratio' in key or key in ['market_cap'] else format_percentage(value) if 'margin' in key or 'roe' in key or 'roa' in key or 'yield' in key else str(value) if value else "N/A"
        }

    return {
        'ticker': ticker,
        'date': today,
        'mode': mode,
        'sections': active_sections,
        'profile': profile,
        'price': price_info,
        'financials': raw_data.get("financials", {}),
        'dividends': raw_data.get("dividends", {}),
        'analyst': raw_data.get("analyst", {}),
        'ownership': raw_data.get("ownership", {}),
        'news': raw_data.get("news", []),
        'metrics': formatted_metrics,
        'charts': charts,
        'is_beginner': mode == 'beginner',
        'is_advanced': mode == 'advanced',
    }


def render_report(template_data: Dict[str, Any], mode: str) -> str:
    """Render HTML report using Jinja2 templates."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(['html', 'xml']),
    )

    # Add custom filters
    env.filters['format_number'] = format_large_number
    env.filters['format_percent'] = format_percentage

    # Load main template
    template = env.get_template("report.html.jinja2")

    # Render with Markup for chart JSON to prevent double-escaping
    for key, chart_data in template_data.get('charts', {}).items():
        if isinstance(chart_data, dict) and 'json' in chart_data:
            template_data['charts'][key]['json'] = Markup(chart_data['json'])

    return template.render(**template_data)


def write_report(html_content: str, ticker: str) -> str:
    """Write HTML to output file atomically."""
    today = datetime.now().strftime("%Y-%m-%d")
    output_path = OUTPUT_DIR / f"{ticker}_{today}.html"

    # Atomic write: write to temp file first, then rename
    with tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.html',
        dir=OUTPUT_DIR,
        delete=False
    ) as f:
        f.write(html_content)
        temp_path = f.name

    # Rename to final path
    os.rename(temp_path, output_path)

    return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Generate interactive HTML financial report"
    )
    parser.add_argument(
        "--ticker", "-t",
        required=True,
        help="Stock ticker symbol (e.g., AAPL, BBCA.JK)"
    )
    parser.add_argument(
        "--mode", "-m",
        choices=["beginner", "advanced"],
        default="beginner",
        help="Report mode: beginner (simplified) or advanced (detailed)"
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Force refresh data, ignore cache"
    )
    args = parser.parse_args()

    ticker = args.ticker.upper()
    mode = args.mode

    # Validate ticker
    if not validate_ticker(ticker):
        print(f"CRITICAL: Invalid ticker format: {ticker}")
        print("Expected format: 1-5 letters, optional .JK or .US suffix")
        sys.exit(1)

    # Initialize database
    init_db()

    warnings = []

    try:
        # Step 1: Fetch data
        print(f"Fetching data for {ticker}...", file=sys.stderr)
        raw_data, fetch_warnings = fetch_all_data(
            ticker,
            force_refresh=args.force_refresh
        )
        warnings.extend(fetch_warnings)

        # Step 2: Compute metrics
        print(f"Computing metrics...", file=sys.stderr)
        metrics, metric_warnings = compute_all_metrics(raw_data, mode)
        warnings.extend(metric_warnings)

        # Step 3: Generate charts
        print(f"Generating charts...", file=sys.stderr)
        charts, chart_warnings = generate_charts(raw_data, mode)
        warnings.extend(chart_warnings)

        # Step 4: Prepare template data
        template_data = prepare_template_data(ticker, raw_data, metrics, charts, mode)

        # Step 5: Render report
        print(f"Rendering report...", file=sys.stderr)
        html_content = render_report(template_data, mode)

        # Step 6: Write output
        output_path = write_report(html_content, ticker)

        # Print stdout contract
        print(f"OUTPUT: {output_path}")

        # Quality metrics
        quality = {
            'price': 'OK' if raw_data.get('price') else 'MISSING',
            'financials': 'OK' if raw_data.get('financials') else 'MISSING',
            'dividends': 'OK' if raw_data.get('dividends') else 'MISSING',
            'news': 'OK' if raw_data.get('news') else 'MISSING',
            'analyst': 'OK' if raw_data.get('analyst') else 'MISSING',
            'ownership': 'OK' if raw_data.get('ownership') else 'MISSING',
        }
        print(f"QUALITY: {' '.join(f'{k}={v}' for k, v in quality.items())}")
        print(f"SECTIONS: {','.join(template_data['sections'])}")

        if warnings:
            print(f"WARNINGS: {'; '.join(warnings)}")

    except Exception as e:
        print(f"CRITICAL: {str(e)}")
        import traceback
        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()