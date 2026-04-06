"""
TradingAgents-CC — Technical Indicators

Computes trend, momentum, volatility, and volume indicators using pandas-ta.
Also provides simple chart pattern detection heuristics.

Every individual indicator computation is wrapped in try/except so that a
failure in one indicator never crashes the whole pipeline — the field is
returned as ``None`` instead.
"""

import math
from typing import Any

import numpy as np
import pandas as pd

from src.utils import setup_logging

logger = setup_logging()


# ---------------------------------------------------------------------------
# Main Indicator Function
# ---------------------------------------------------------------------------

def compute_indicators(df: pd.DataFrame) -> dict[str, Any]:
    """Compute all technical indicators on an OHLCV DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must have columns: Open, High, Low, Close, Volume (case-insensitive)
        with a DatetimeIndex.

    Returns
    -------
    dict
        Dictionary of latest indicator values.  Individual fields may be
        ``None`` if computation failed.
    """
    # Normalise column names
    df = df.copy()
    df.columns = [c.strip().capitalize() for c in df.columns]

    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(set(df.columns)):
        logger.error("OHLCV columns missing. Got: %s", list(df.columns))
        return {}

    # Try importing pandas_ta
    try:
        import pandas_ta as ta  # type: ignore
    except ImportError:
        logger.error("pandas_ta not installed — cannot compute indicators")
        return {}

    result: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Trend Indicators
    # ------------------------------------------------------------------

    result["sma_20"] = _safe_last(lambda: ta.sma(df["Close"], length=20))
    result["sma_50"] = _safe_last(lambda: ta.sma(df["Close"], length=50))
    result["sma_200"] = _safe_last(lambda: ta.sma(df["Close"], length=200))
    result["ema_12"] = _safe_last(lambda: ta.ema(df["Close"], length=12))
    result["ema_26"] = _safe_last(lambda: ta.ema(df["Close"], length=26))

    # MACD
    try:
        macd_df = ta.macd(df["Close"], fast=12, slow=26, signal=9)
        if macd_df is not None and not macd_df.empty:
            cols = macd_df.columns.tolist()
            result["macd"] = _last_val(macd_df.iloc[:, 0])
            result["macd_signal"] = _last_val(macd_df.iloc[:, 1]) if len(cols) > 1 else None
            result["macd_histogram"] = _last_val(macd_df.iloc[:, 2]) if len(cols) > 2 else None
        else:
            result["macd"] = result["macd_signal"] = result["macd_histogram"] = None
    except Exception as exc:
        logger.warning("MACD computation failed: %s", exc)
        result["macd"] = result["macd_signal"] = result["macd_histogram"] = None

    # ADX
    try:
        adx_df = ta.adx(df["High"], df["Low"], df["Close"], length=14)
        if adx_df is not None and not adx_df.empty:
            adx_col = [c for c in adx_df.columns if "ADX" in c.upper() and "DM" not in c.upper()]
            result["adx"] = _last_val(adx_df[adx_col[0]]) if adx_col else None
        else:
            result["adx"] = None
    except Exception as exc:
        logger.warning("ADX computation failed: %s", exc)
        result["adx"] = None

    # ------------------------------------------------------------------
    # Momentum Indicators
    # ------------------------------------------------------------------

    result["rsi_14"] = _safe_last(lambda: ta.rsi(df["Close"], length=14))

    # Stochastic
    try:
        stoch_df = ta.stoch(df["High"], df["Low"], df["Close"], k=14, d=3, smooth_k=3)
        if stoch_df is not None and not stoch_df.empty:
            result["stochastic_k"] = _last_val(stoch_df.iloc[:, 0])
            result["stochastic_d"] = _last_val(stoch_df.iloc[:, 1]) if stoch_df.shape[1] > 1 else None
        else:
            result["stochastic_k"] = result["stochastic_d"] = None
    except Exception as exc:
        logger.warning("Stochastic computation failed: %s", exc)
        result["stochastic_k"] = result["stochastic_d"] = None

    result["roc_10"] = _safe_last(lambda: ta.roc(df["Close"], length=10))

    # ------------------------------------------------------------------
    # Volatility Indicators
    # ------------------------------------------------------------------

    # Bollinger Bands
    try:
        bb_df = ta.bbands(df["Close"], length=20, std=2)
        if bb_df is not None and not bb_df.empty:
            cols = bb_df.columns.tolist()
            lower_cols = [c for c in cols if "BBL" in c.upper()]
            mid_cols = [c for c in cols if "BBM" in c.upper()]
            upper_cols = [c for c in cols if "BBU" in c.upper()]
            result["bb_upper"] = _last_val(bb_df[upper_cols[0]]) if upper_cols else None
            result["bb_mid"] = _last_val(bb_df[mid_cols[0]]) if mid_cols else None
            result["bb_lower"] = _last_val(bb_df[lower_cols[0]]) if lower_cols else None
        else:
            result["bb_upper"] = result["bb_mid"] = result["bb_lower"] = None
    except Exception as exc:
        logger.warning("Bollinger Bands computation failed: %s", exc)
        result["bb_upper"] = result["bb_mid"] = result["bb_lower"] = None

    result["atr_14"] = _safe_last(
        lambda: ta.atr(df["High"], df["Low"], df["Close"], length=14)
    )

    # Historical volatility (20-day annualized)
    try:
        log_returns = np.log(df["Close"] / df["Close"].shift(1)).dropna()
        hv = float(log_returns.tail(20).std() * np.sqrt(252))
        result["historical_volatility_20d"] = round(hv, 6) if not math.isnan(hv) else None
    except Exception:
        result["historical_volatility_20d"] = None

    # ------------------------------------------------------------------
    # Volume Indicators
    # ------------------------------------------------------------------

    result["obv"] = _safe_last(lambda: ta.obv(df["Close"], df["Volume"]))
    result["vwap"] = _safe_last(
        lambda: ta.vwap(df["High"], df["Low"], df["Close"], df["Volume"])
    )
    result["volume_sma_20"] = _safe_last(lambda: ta.sma(df["Volume"], length=20))
    result["volume"] = _last_val(df["Volume"])  # Current volume for skill rules

    # ------------------------------------------------------------------
    # Current price & 52-week range
    # ------------------------------------------------------------------

    result["current_price"] = _last_val(df["Close"])

    try:
        last_252 = df["Close"].tail(252)
        result["52w_high"] = float(last_252.max())
        result["52w_low"] = float(last_252.min())
    except Exception:
        result["52w_high"] = result["52w_low"] = None

    # ------------------------------------------------------------------
    # Support / Resistance (rolling pivot)
    # ------------------------------------------------------------------

    support_levels = _find_swing_levels(df, kind="low", n=3, window=90)
    resistance_levels = _find_swing_levels(df, kind="high", n=3, window=90)

    # ------------------------------------------------------------------
    # Restructure output to match skill expectations
    # ------------------------------------------------------------------

    # Extract indicator subset for nested structure
    indicators = {
        "sma_20": result.get("sma_20"),
        "sma_50": result.get("sma_50"),
        "sma_200": result.get("sma_200"),
        "rsi_14": result.get("rsi_14"),
        "macd": result.get("macd"),
        "macd_signal": result.get("macd_signal"),
        "macd_histogram": result.get("macd_histogram"),
        "adx": result.get("adx"),
        "bb_upper": result.get("bb_upper"),
        "bb_lower": result.get("bb_lower"),
        "atr_14": result.get("atr_14"),
        "52w_high": result.get("52w_high"),
        "52w_low": result.get("52w_low"),
        # Additional indicators needed for skill interpretation rules
        "stochastic_k": result.get("stochastic_k"),
        "stochastic_d": result.get("stochastic_d"),
        "obv": result.get("obv"),
        "volume_sma_20": result.get("volume_sma_20"),
        "volume": result.get("volume"),
    }

    # Key levels as dict with support_1, support_2, etc.
    key_levels = {
        "support_1": support_levels[0] if len(support_levels) > 0 else None,
        "support_2": support_levels[1] if len(support_levels) > 1 else None,
        "resistance_1": resistance_levels[0] if len(resistance_levels) > 0 else None,
        "resistance_2": resistance_levels[1] if len(resistance_levels) > 1 else None,
    }

    # Return structured output matching skill expectations
    return {
        "current_price": result.get("current_price"),
        "indicators": indicators,
        "votes": {
            "trend": None,  # Computed by skill based on interpretation rules
            "momentum": None,
            "volume": None,
        },
        "scores": {
            "trend_score": None,
            "momentum_score": None,
            "volume_confirmation": None,
            "total_signal_score": None,
        },
        "technical_signal": None,  # Computed by skill
        "chart_pattern": None,  # Will be added by caller
        "key_levels": key_levels,
        "high_volatility_flag": (result.get("atr_14") or 0) / (result.get("current_price") or 1) > 0.03,
        # Keep raw values for skill to compute scores
        "_raw": result,
    }


# ---------------------------------------------------------------------------
# Chart Pattern Detection
# ---------------------------------------------------------------------------

def detect_chart_pattern(df: pd.DataFrame) -> dict[str, Any]:
    """Heuristic chart pattern detection.

    Returns
    -------
    dict with keys: pattern (str|None), confidence (float), description (str)
    """
    df = df.copy()
    df.columns = [c.strip().capitalize() for c in df.columns]
    close = df["Close"].values
    n = len(close)

    if n < 60:
        return {"pattern": None, "confidence": 0.0, "description": "Insufficient data"}

    result: dict[str, Any] = {"pattern": None, "confidence": 0.0, "description": ""}

    # --- Double Bottom ---
    try:
        window = close[-60:]
        mid = len(window) // 2
        left_min = window[:mid].min()
        right_min = window[mid:].min()
        left_idx = int(window[:mid].argmin())
        right_idx = mid + int(window[mid:].argmin())
        peak = window[left_idx:right_idx].max()

        tolerance = 0.03  # 3%
        if abs(left_min - right_min) / left_min < tolerance and peak > left_min * 1.03:
            if close[-1] > peak:  # breakout confirmation
                result = {
                    "pattern": "Double Bottom",
                    "confidence": 0.75,
                    "description": (
                        f"Two lows near ${left_min:.2f} with neckline breakout "
                        f"above ${peak:.2f}."
                    ),
                }
    except Exception:
        pass

    # --- Double Top ---
    if result["pattern"] is None:
        try:
            window = close[-60:]
            mid = len(window) // 2
            left_max = window[:mid].max()
            right_max = window[mid:].max()
            left_idx = int(window[:mid].argmax())
            right_idx = mid + int(window[mid:].argmax())
            trough = window[left_idx:right_idx].min()

            if abs(left_max - right_max) / left_max < 0.03 and trough < left_max * 0.97:
                if close[-1] < trough:
                    result = {
                        "pattern": "Double Top",
                        "confidence": 0.72,
                        "description": (
                            f"Two highs near ${left_max:.2f} with neckline break "
                            f"below ${trough:.2f}."
                        ),
                    }
        except Exception:
            pass

    # --- Head & Shoulders (simplified) ---
    if result["pattern"] is None and n >= 90:
        try:
            window = close[-90:]
            third = len(window) // 3
            left_peak = window[:third].max()
            head_peak = window[third : 2 * third].max()
            right_peak = window[2 * third :].max()

            if (
                head_peak > left_peak * 1.02
                and head_peak > right_peak * 1.02
                and abs(left_peak - right_peak) / left_peak < 0.05
            ):
                result = {
                    "pattern": "Head and Shoulders",
                    "confidence": 0.65,
                    "description": (
                        f"Head at ${head_peak:.2f} with shoulders near "
                        f"${left_peak:.2f} / ${right_peak:.2f}."
                    ),
                }
        except Exception:
            pass

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_last(fn) -> Any:
    """Call *fn* (which returns a Series/scalar) and return last non-NaN value."""
    try:
        series = fn()
        if series is None:
            return None
        return _last_val(series)
    except Exception as exc:
        logger.debug("Indicator failed: %s", exc)
        return None


def _last_val(series) -> Any:
    """Extract the last non-NaN scalar from a pandas Series."""
    if series is None:
        return None
    if isinstance(series, (int, float, np.integer, np.floating)):
        v = float(series)
        return round(v, 6) if not math.isnan(v) else None
    try:
        v = float(series.dropna().iloc[-1])
        return round(v, 6) if not math.isnan(v) else None
    except (IndexError, TypeError, ValueError):
        return None


def _find_swing_levels(
    df: pd.DataFrame, kind: str = "low", n: int = 3, window: int = 90
) -> list[float]:
    """Identify the last *n* swing highs or lows within *window* bars."""
    col = "Low" if kind == "low" else "High"
    try:
        data = df[col].tail(window).values
        levels: list[float] = []
        order = 5  # bars on each side for a swing

        for i in range(order, len(data) - order):
            if kind == "low":
                if all(data[i] <= data[i - j] for j in range(1, order + 1)) and all(
                    data[i] <= data[i + j] for j in range(1, order + 1)
                ):
                    levels.append(round(float(data[i]), 2))
            else:
                if all(data[i] >= data[i - j] for j in range(1, order + 1)) and all(
                    data[i] >= data[i + j] for j in range(1, order + 1)
                ):
                    levels.append(round(float(data[i]), 2))

        # Return last n unique levels
        seen: set[float] = set()
        unique: list[float] = []
        for lev in reversed(levels):
            if lev not in seen:
                seen.add(lev)
                unique.append(lev)
            if len(unique) >= n:
                break
        return unique
    except Exception:
        return []
