"""Financial metric calculations with validation."""
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from pipeline.config import METRIC_THRESHOLDS


def safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    """Safe division that returns None for invalid denominators."""
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        return None
    try:
        result = numerator / denominator
        if abs(result) > 1e9:  # Sanity check
            return None
        return result
    except (TypeError, ZeroDivisionError, ValueError):
        return None


def round_metric(value: Optional[float], decimals: int = 2) -> Optional[float]:
    """Round metric to specified decimals."""
    if value is None:
        return None
    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return None


def calculate_roe(net_income: Optional[float], total_equity: Optional[float]) -> Optional[float]:
    """Return on Equity = Net Income / Total Equity."""
    return round_metric(safe_divide(net_income, total_equity) * 100 if net_income and total_equity else None, 1)


def calculate_roa(net_income: Optional[float], total_assets: Optional[float]) -> Optional[float]:
    """Return on Assets = Net Income / Total Assets."""
    return round_metric(safe_divide(net_income, total_assets) * 100 if net_income and total_assets else None, 1)


def calculate_net_margin(net_income: Optional[float], total_revenue: Optional[float]) -> Optional[float]:
    """Net Profit Margin = Net Income / Total Revenue."""
    return round_metric(safe_divide(net_income, total_revenue) * 100 if net_income and total_revenue else None, 1)


def calculate_gross_margin(gross_profit: Optional[float], total_revenue: Optional[float]) -> Optional[float]:
    """Gross Margin = Gross Profit / Total Revenue."""
    return round_metric(safe_divide(gross_profit, total_revenue) * 100 if gross_profit and total_revenue else None, 1)


def calculate_debt_equity(total_debt: Optional[float], total_equity: Optional[float]) -> Optional[float]:
    """Debt to Equity Ratio = Total Debt / Total Equity."""
    return round_metric(safe_divide(total_debt, total_equity))


def calculate_debt_assets(total_debt: Optional[float], total_assets: Optional[float]) -> Optional[float]:
    """Debt to Assets Ratio = Total Debt / Total Assets."""
    return round_metric(safe_divide(total_debt, total_assets))


def calculate_pe_ratio(market_cap: Optional[float], net_income: Optional[float]) -> Optional[float]:
    """Price to Earnings Ratio = Market Cap / Net Income."""
    return round_metric(safe_divide(market_cap, net_income))


def calculate_pb_ratio(market_cap: Optional[float], total_equity: Optional[float]) -> Optional[float]:
    """Price to Book Ratio = Market Cap / Total Equity."""
    return round_metric(safe_divide(market_cap, total_equity))


def calculate_ps_ratio(market_cap: Optional[float], total_revenue: Optional[float]) -> Optional[float]:
    """Price to Sales Ratio = Market Cap / Total Revenue."""
    return round_metric(safe_divide(market_cap, total_revenue))


def calculate_pcf_ratio(market_cap: Optional[float], operating_cashflow: Optional[float]) -> Optional[float]:
    """Price to Cash Flow Ratio = Market Cap / Operating Cash Flow."""
    return round_metric(safe_divide(market_cap, operating_cashflow))


def calculate_peg_ratio(pe_ratio: Optional[float], earnings_growth: Optional[float]) -> Optional[float]:
    """PEG Ratio = P/E Ratio / Earnings Growth Rate."""
    if pe_ratio is None or earnings_growth is None or earnings_growth == 0:
        return None
    return round_metric(safe_divide(pe_ratio, earnings_growth))


def calculate_ev_ebitda(
    market_cap: Optional[float],
    total_debt: Optional[float],
    cash: Optional[float],
    ebitda: Optional[float]
) -> Optional[float]:
    """EV/EBITDA = (Market Cap + Debt - Cash) / EBITDA."""
    if market_cap is None or ebitda is None or ebitda == 0:
        return None

    enterprise_value = market_cap
    if total_debt:
        enterprise_value += total_debt
    if cash:
        enterprise_value -= cash

    return round_metric(safe_divide(enterprise_value, ebitda))


def calculate_dividend_yield(ttm_dividend: Optional[float], current_price: Optional[float]) -> Optional[float]:
    """Dividend Yield = (TTM Dividend / Current Price) * 100."""
    if ttm_dividend is None or current_price is None or current_price == 0:
        return None
    return round_metric((ttm_dividend / current_price) * 100, 2)


def calculate_payout_ratio(total_dividends: Optional[float], net_income: Optional[float]) -> Optional[float]:
    """Payout Ratio = Total Dividends / Net Income."""
    return round_metric(safe_divide(total_dividends, net_income) * 100 if total_dividends and net_income else None, 1)


def calculate_yoy_growth(current: Optional[float], year_ago: Optional[float]) -> Optional[float]:
    """Year over Year Growth = ((Current - Year Ago) / Year Ago) * 100."""
    if current is None or year_ago is None or year_ago == 0:
        return None
    return round_metric(((current - year_ago) / abs(year_ago)) * 100, 1)


def calculate_cagr(beginning_value: float, ending_value: float, years: int) -> Optional[float]:
    """Compound Annual Growth Rate."""
    if beginning_value is None or ending_value is None or years is None or years <= 0:
        return None
    if beginning_value <= 0 or ending_value <= 0:
        return None
    try:
        cagr = ((ending_value / beginning_value) ** (1 / years)) - 1
        return round_metric(cagr * 100, 1)
    except (ValueError, ZeroDivisionError):
        return None


def calculate_rsi(prices: pd.Series, period: int = 14) -> Optional[float]:
    """Calculate Relative Strength Index."""
    if len(prices) < period:
        return None

    try:
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = safe_divide(gain.iloc[-1], loss.iloc[-1])
        if rs is None:
            return None

        rsi = 100 - (100 / (1 + rs))
        return round_metric(rsi, 1)
    except Exception as e:
        print(f"RSI calculation error: {e}", file=sys.stderr)
        return None


def calculate_sma(prices: pd.Series, period: int) -> Optional[float]:
    """Calculate Simple Moving Average."""
    if len(prices) < period:
        return None
    return round_metric(prices.tail(period).mean(), 2)


def calculate_ema(prices: pd.Series, period: int) -> Optional[float]:
    """Calculate Exponential Moving Average."""
    if len(prices) < period:
        return None
    return round_metric(prices.ewm(span=period, adjust=False).mean().iloc[-1], 2)


def calculate_macd(prices: pd.Series) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Calculate MACD, Signal, and Histogram."""
    if len(prices) < 26:
        return None, None, None

    try:
        ema_12 = prices.ewm(span=12, adjust=False).mean()
        ema_26 = prices.ewm(span=26, adjust=False).mean()
        macd = ema_12 - ema_26
        signal = macd.ewm(span=9, adjust=False).mean()
        histogram = macd - signal

        return (
            round_metric(macd.iloc[-1], 4),
            round_metric(signal.iloc[-1], 4),
            round_metric(histogram.iloc[-1], 4)
        )
    except Exception as e:
        print(f"MACD calculation error: {e}", file=sys.stderr)
        return None, None, None


def calculate_bollinger_bands(prices: pd.Series, period: int = 20) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Calculate Bollinger Bands (Upper, Middle, Lower)."""
    if len(prices) < period:
        return None, None, None

    try:
        sma = prices.rolling(window=period).mean()
        std = prices.rolling(window=period).std()

        upper = sma + (2 * std)
        lower = sma - (2 * std)

        return (
            round_metric(upper.iloc[-1], 2),
            round_metric(sma.iloc[-1], 2),
            round_metric(lower.iloc[-1], 2)
        )
    except Exception as e:
        print(f"Bollinger calculation error: {e}", file=sys.stderr)
        return None, None, None


def compute_price_metrics(price_data: Optional[Dict]) -> Dict[str, Optional[float]]:
    """Compute price-related metrics."""
    metrics = {}

    if not price_data or not price_data.get("history"):
        return {
            "sma_20": None, "sma_50": None, "sma_200": None,
            "rsi": None, "macd": None, "macd_signal": None,
            "bb_upper": None, "bb_middle": None, "bb_lower": None,
        }

    try:
        history = price_data["history"]
        if isinstance(history, list):
            df = pd.DataFrame(history)
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], utc=True)
                df = df.set_index('Date')
            prices = df['Close']
        else:
            prices = pd.Series([h.get('Close', h.get('close', 0)) for h in history])

        # SMAs
        metrics["sma_20"] = calculate_sma(prices, 20)
        metrics["sma_50"] = calculate_sma(prices, 50)
        metrics["sma_200"] = calculate_sma(prices, 200)

        # RSI
        metrics["rsi"] = calculate_rsi(prices, 14)

        # MACD
        macd, signal, _ = calculate_macd(prices)
        metrics["macd"] = macd
        metrics["macd_signal"] = signal

        # Bollinger Bands
        bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(prices, 20)
        metrics["bb_upper"] = bb_upper
        metrics["bb_middle"] = bb_middle
        metrics["bb_lower"] = bb_lower

    except Exception as e:
        print(f"Price metrics calculation error: {e}", file=sys.stderr)

    return metrics


def compute_financial_metrics(financials: Optional[Dict], price_data: Optional[Dict]) -> Dict[str, Optional[float]]:
    """Compute financial metrics from statements."""
    metrics = {}

    if not financials:
        return metrics

    info = financials.get("info", {})

    # Profitability
    metrics["roe"] = calculate_roe(
        info.get("net_income"),
        info.get("total_equity")
    )
    metrics["roa"] = calculate_roa(
        info.get("net_income"),
        info.get("total_assets")
    )
    metrics["net_margin"] = calculate_net_margin(
        info.get("net_income"),
        info.get("total_revenue")
    )
    metrics["gross_margin"] = calculate_gross_margin(
        info.get("gross_profits"),
        info.get("total_revenue")
    )

    # Leverage
    metrics["debt_equity"] = calculate_debt_equity(
        info.get("total_debt"),
        info.get("total_equity")
    )
    metrics["debt_assets"] = calculate_debt_assets(
        info.get("total_debt"),
        info.get("total_assets")
    )

    # Valuation (from price data)
    if price_data:
        market_cap = price_data.get("market_cap")
        metrics["pe_ratio"] = calculate_pe_ratio(market_cap, info.get("net_income"))
        metrics["pb_ratio"] = calculate_pb_ratio(market_cap, info.get("total_equity"))
        metrics["ps_ratio"] = calculate_ps_ratio(market_cap, info.get("total_revenue"))
        metrics["pcf_ratio"] = calculate_pcf_ratio(market_cap, info.get("operating_cashflow"))

        # Advanced valuation metrics
        # Use net income growth rate for PEG (approximation)
        income_stmt = financials.get("income_statement", [])
        if len(income_stmt) >= 4 and metrics.get("pe_ratio"):
            current_ni = income_stmt[0].get("Net Income")
            year_ago_ni = income_stmt[3].get("Net Income")
            if current_ni and year_ago_ni and year_ago_ni != 0:
                earnings_growth = ((current_ni - year_ago_ni) / abs(year_ago_ni)) * 100
                metrics["peg_ratio"] = calculate_peg_ratio(metrics["pe_ratio"], earnings_growth)

        # EV/EBITDA
        metrics["ev_ebitda"] = calculate_ev_ebitda(
            market_cap,
            info.get("total_debt"),
            None,  # Cash - would need from balance sheet
            info.get("ebitda")
        )

    return metrics


def compute_dividend_metrics(dividends: Optional[Dict], price_data: Optional[Dict]) -> Dict[str, Optional[float]]:
    """Compute dividend-related metrics."""
    metrics = {}

    if not dividends:
        return metrics

    current_price = None
    if price_data:
        current_price = price_data.get("current_price")

    ttm_dividend = dividends.get("ttm_dividend")
    metrics["dividend_yield"] = calculate_dividend_yield(ttm_dividend, current_price)

    # Calculate 5-year CAGR if enough history
    history = dividends.get("history", [])
    if len(history) >= 20:  # ~5 years of quarterly dividends
        try:
            oldest = history[0]["amount"]
            newest = history[-1]["amount"]
            years = len(history) / 4  # Approximate years
            metrics["dividend_cagr_5y"] = calculate_cagr(oldest, newest, years)
        except:
            metrics["dividend_cagr_5y"] = None

    return metrics


def compute_growth_metrics(financials: Optional[Dict]) -> Dict[str, Optional[float]]:
    """Compute growth metrics from historical financials."""
    metrics = {}

    if not financials:
        return metrics

    income_stmt = financials.get("income_statement", [])
    if len(income_stmt) < 4:
        return metrics

    try:
        # Revenue growth (YoY)
        current_revenue = income_stmt[0].get("Total Revenue") or income_stmt[0].get("totalRevenue")
        year_ago_revenue = income_stmt[3].get("Total Revenue") or income_stmt[3].get("totalRevenue")
        metrics["revenue_yoy"] = calculate_yoy_growth(current_revenue, year_ago_revenue)

        # Net income growth (YoY)
        current_net_income = income_stmt[0].get("Net Income") or income_stmt[0].get("netIncome")
        year_ago_net_income = income_stmt[3].get("Net Income") or income_stmt[3].get("netIncome")
        metrics["net_income_yoy"] = calculate_yoy_growth(current_net_income, year_ago_net_income)

    except Exception as e:
        print(f"Growth metrics calculation error: {e}", file=sys.stderr)

    return metrics


def compute_all_metrics(
    raw_data: Dict[str, Any],
    mode: str = "beginner"
) -> Tuple[Dict[str, Optional[float]], List[str]]:
    """
    Compute all metrics with validation.

    Returns: (metrics_dict, warnings_list)
    """
    warnings = []
    metrics = {}

    price_data = raw_data.get("price")
    financials = raw_data.get("financials")
    dividends = raw_data.get("dividends")

    # Price metrics (always include for advanced mode)
    if mode == "advanced" and price_data:
        price_metrics = compute_price_metrics(price_data)
        metrics.update(price_metrics)

        # Validation warnings
        if price_metrics.get("rsi") is None:
            warnings.append("RSI skipped: insufficient price history (< 14 days)")
        if price_metrics.get("sma_200") is None:
            warnings.append("SMA 200 skipped: insufficient price history (< 200 days)")
        if price_metrics.get("bb_upper") is None:
            warnings.append("Bollinger Bands skipped: insufficient price history (< 30 days)")

    # Financial metrics
    financial_metrics = compute_financial_metrics(financials, price_data)
    metrics.update(financial_metrics)

    # Dividend metrics
    dividend_metrics = compute_dividend_metrics(dividends, price_data)
    metrics.update(dividend_metrics)

    # Growth metrics
    growth_metrics = compute_growth_metrics(financials)
    metrics.update(growth_metrics)

    if financials and len(financials.get("income_statement", [])) < 4:
        warnings.append("YoY growth skipped: insufficient financial history (< 4 quarters)")

    # Count computed vs skipped
    computed = sum(1 for v in metrics.values() if v is not None)
    skipped = sum(1 for v in metrics.values() if v is None)

    print(f"ANALYZE: metrics_computed={computed} skipped={skipped} mode={mode}", file=sys.stderr)

    return metrics, warnings