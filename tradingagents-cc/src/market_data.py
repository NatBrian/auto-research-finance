"""
TradingAgents-CC — Market Data Client

Wraps yfinance to provide price history, financials, valuation metrics,
earnings, insider transactions, options flow, short interest, and analyst
ratings.  Implements parquet-based caching for price data.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

from src.utils import (
    DataUnavailableError,
    get_project_root,
    safe_json_dumps,
    setup_logging,
)

logger = setup_logging()


class MarketDataClient:
    """Unified market data interface backed by yfinance."""

    def __init__(self) -> None:
        self._cache_dir = get_project_root() / "data" / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Price History
    # ------------------------------------------------------------------

    def get_price_history(
        self,
        ticker: str,
        end_date: str,
        lookback_days: int = 365,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """Fetch OHLCV price history with parquet caching.

        Parameters
        ----------
        ticker : str
        end_date : str  (YYYY-MM-DD)
        lookback_days : int
        interval : str  ("1d", "1h", etc.)

        Returns
        -------
        pd.DataFrame  with DatetimeIndex and OHLCV columns

        Raises
        ------
        DataUnavailableError
        """
        end_dt = pd.Timestamp(end_date)
        start_dt = end_dt - pd.Timedelta(days=lookback_days)
        start_str = start_dt.strftime("%Y-%m-%d")
        end_str = end_dt.strftime("%Y-%m-%d")

        cache_key = f"prices_{ticker}_{start_str}_{end_str}_{interval}.parquet"
        cache_path = self._cache_dir / cache_key

        if cache_path.exists():
            logger.info("Cache hit: %s", cache_path.name)
            return pd.read_parquet(cache_path)

        try:
            df = yf.download(
                ticker,
                start=start_str,
                end=end_str,
                interval=interval,
                auto_adjust=True,
                progress=False,
            )
        except Exception as exc:
            raise DataUnavailableError(
                f"Failed to download price data for {ticker}: {exc}"
            ) from exc

        if df is None or df.empty:
            raise DataUnavailableError(
                f"No price data returned for {ticker} "
                f"({start_str} to {end_str}, interval={interval})"
            )

        # Flatten multi-level columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Save to cache
        try:
            df.to_parquet(cache_path)
            logger.info("Cached prices to %s", cache_path.name)
        except Exception as exc:
            logger.warning("Could not cache price data: %s", exc)

        return df

    # ------------------------------------------------------------------
    # Financials
    # ------------------------------------------------------------------

    def get_financials(self, ticker: str, date: str) -> dict[str, Any]:
        """Return income statement, balance sheet, and cash flow data."""
        try:
            t = yf.Ticker(ticker)
            result = {
                "income_statement": self._df_to_safe(t.income_stmt),
                "balance_sheet": self._df_to_safe(t.balance_sheet),
                "cash_flow": self._df_to_safe(t.cashflow),
            }
            return result
        except Exception as exc:
            raise DataUnavailableError(
                f"Failed to fetch financials for {ticker}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Valuation Metrics
    # ------------------------------------------------------------------

    def get_valuation_metrics(self, ticker: str, date: str) -> dict[str, Any]:
        """Extract key valuation ratios from yfinance info."""
        try:
            info = yf.Ticker(ticker).info or {}
        except Exception as exc:
            raise DataUnavailableError(
                f"Failed to fetch valuation metrics for {ticker}: {exc}"
            ) from exc

        keys = [
            "trailingPE", "forwardPE", "priceToBook",
            "priceToSalesTrailing12Months", "enterpriseToEbitda",
            "pegRatio", "marketCap", "currentPrice", "targetMeanPrice",
        ]
        return {k: info.get(k) for k in keys}

    # ------------------------------------------------------------------
    # Earnings History
    # ------------------------------------------------------------------

    def get_earnings_history(self, ticker: str, n_quarters: int = 8) -> list[dict]:
        """Return recent quarterly earnings surprises."""
        try:
            t = yf.Ticker(ticker)
            # Try earnings_dates first (newer yfinance)
            try:
                eh = t.earnings_dates
                if eh is not None and not eh.empty:
                    records = []
                    for idx, row in eh.head(n_quarters).iterrows():
                        records.append({
                            "date": str(idx.date()) if hasattr(idx, "date") else str(idx),
                            "reported_eps": self._safe_val(row.get("Reported EPS")),
                            "estimated_eps": self._safe_val(row.get("EPS Estimate")),
                            "surprise_pct": self._safe_val(row.get("Surprise(%)")),
                        })
                    return records
            except Exception:
                pass

            # Fallback to quarterly_earnings
            try:
                qe = t.quarterly_earnings
                if qe is not None and not qe.empty:
                    records = []
                    for idx, row in qe.head(n_quarters).iterrows():
                        records.append({
                            "date": str(idx),
                            "reported_eps": self._safe_val(row.get("Earnings")),
                            "estimated_eps": None,
                            "surprise_pct": None,
                        })
                    return records
            except Exception:
                pass

            return []
        except Exception as exc:
            raise DataUnavailableError(
                f"Failed to fetch earnings history for {ticker}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Insider Transactions
    # ------------------------------------------------------------------

    def get_insider_transactions(
        self, ticker: str, lookback_days: int = 90
    ) -> list[dict]:
        """Return insider buy/sell transactions within lookback window."""
        try:
            t = yf.Ticker(ticker)
            txns = t.insider_transactions
            if txns is None or txns.empty:
                return []

            cutoff = datetime.now() - timedelta(days=lookback_days)
            records = []
            for _, row in txns.iterrows():
                row_date = row.get("Start Date") or row.get("Date")
                if row_date is not None:
                    if isinstance(row_date, str):
                        try:
                            row_date = pd.Timestamp(row_date)
                        except Exception:
                            continue
                    if hasattr(row_date, "to_pydatetime"):
                        row_date = row_date.to_pydatetime()
                    if hasattr(row_date, "replace"):
                        if row_date.tzinfo:
                            row_date = row_date.replace(tzinfo=None)
                    try:
                        if row_date < cutoff:
                            continue
                    except TypeError:
                        pass

                records.append({
                    "date": str(row_date),
                    "insider_name": row.get("Insider") or row.get("Name", "Unknown"),
                    "transaction_type": row.get("Transaction") or row.get("Type", ""),
                    "shares": self._safe_val(row.get("Shares")),
                    "value": self._safe_val(row.get("Value")),
                })
            return records
        except Exception as exc:
            logger.warning("Insider transactions unavailable for %s: %s", ticker, exc)
            return []

    # ------------------------------------------------------------------
    # Options Flow
    # ------------------------------------------------------------------

    def get_options_flow(self, ticker: str, date: str) -> dict[str, Any]:
        """Compute put/call ratio and detect unusual options activity."""
        try:
            t = yf.Ticker(ticker)
            expirations = t.options
            if not expirations:
                return {"put_call_ratio": None, "unusual_activity": False, "net_delta": 0.0}

            # Use nearest expiry
            chain = t.option_chain(expirations[0])
            calls = chain.calls
            puts = chain.puts

            total_call_vol = calls["volume"].sum() if "volume" in calls.columns else 0
            total_put_vol = puts["volume"].sum() if "volume" in puts.columns else 0

            pcr = (
                float(total_put_vol / total_call_vol)
                if total_call_vol > 0
                else None
            )

            # Detect unusual activity: any strike with volume > 10x open interest
            unusual = False
            for df_opts in [calls, puts]:
                if "volume" in df_opts.columns and "openInterest" in df_opts.columns:
                    mask = df_opts["volume"] > (df_opts["openInterest"] * 10)
                    if mask.any():
                        unusual = True
                        break

            return {
                "put_call_ratio": round(pcr, 4) if pcr is not None else None,
                "unusual_activity": unusual,
                "net_delta": 0.0,  # Simplified — full delta calc requires option greeks
            }
        except Exception as exc:
            logger.warning("Options flow unavailable for %s: %s", ticker, exc)
            return {"put_call_ratio": None, "unusual_activity": False, "net_delta": 0.0}

    # ------------------------------------------------------------------
    # Short Interest
    # ------------------------------------------------------------------

    def get_short_interest(self, ticker: str) -> dict[str, Any]:
        """Return short interest data from yfinance info."""
        try:
            info = yf.Ticker(ticker).info or {}
            return {
                "short_interest_pct": info.get("shortPercentOfFloat"),
                "days_to_cover": info.get("shortRatio"),
            }
        except Exception as exc:
            logger.warning("Short interest unavailable for %s: %s", ticker, exc)
            return {"short_interest_pct": None, "days_to_cover": None}

    # ------------------------------------------------------------------
    # Analyst Ratings
    # ------------------------------------------------------------------

    def get_analyst_ratings(self, ticker: str) -> dict[str, Any]:
        """Return analyst consensus and price targets."""
        try:
            t = yf.Ticker(ticker)
            info = t.info or {}

            # Recommendations summary
            rec_summary = None
            try:
                rec_summary = t.recommendations_summary
            except Exception:
                pass

            buy_count = hold_count = sell_count = 0
            if rec_summary is not None and not rec_summary.empty:
                row = rec_summary.iloc[0] if len(rec_summary) > 0 else {}
                buy_count = int(row.get("strongBuy", 0)) + int(row.get("buy", 0))
                hold_count = int(row.get("hold", 0))
                sell_count = int(row.get("sell", 0)) + int(row.get("strongSell", 0))

            # Determine consensus
            total = buy_count + hold_count + sell_count
            if total > 0:
                if buy_count / total > 0.6:
                    consensus = "Buy"
                elif sell_count / total > 0.4:
                    consensus = "Sell"
                else:
                    consensus = "Hold"
            else:
                consensus = info.get("recommendationKey", "N/A")

            # Recent upgrades/downgrades
            recent_upgrades = recent_downgrades = 0
            try:
                recs = t.recommendations
                if recs is not None and not recs.empty:
                    recent = recs.tail(10)
                    for _, r in recent.iterrows():
                        grade = str(r.get("To Grade", "")).lower()
                        from_grade = str(r.get("From Grade", "")).lower()
                        if grade in ("buy", "strong buy", "outperform", "overweight"):
                            if from_grade in ("hold", "neutral", "sell", "underperform"):
                                recent_upgrades += 1
                        elif grade in ("sell", "underperform", "underweight"):
                            if from_grade in ("buy", "hold", "neutral", "outperform"):
                                recent_downgrades += 1
            except Exception:
                pass

            return {
                "consensus_rating": consensus,
                "price_target_avg": info.get("targetMeanPrice"),
                "price_target_high": info.get("targetHighPrice"),
                "price_target_low": info.get("targetLowPrice"),
                "buy_count": buy_count,
                "hold_count": hold_count,
                "sell_count": sell_count,
                "recent_upgrades": recent_upgrades,
                "recent_downgrades": recent_downgrades,
            }
        except Exception as exc:
            logger.warning("Analyst ratings unavailable for %s: %s", ticker, exc)
            return {
                "consensus_rating": "N/A",
                "price_target_avg": None,
                "buy_count": 0,
                "hold_count": 0,
                "sell_count": 0,
                "recent_upgrades": 0,
                "recent_downgrades": 0,
            }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _df_to_safe(df: pd.DataFrame | None) -> list[dict]:
        """Convert a DataFrame to a JSON-safe list of records."""
        if df is None or df.empty:
            return []
        df = df.copy()
        df.columns = [str(c) for c in df.columns]
        df.index = [str(i) for i in df.index]
        return df.reset_index().to_dict(orient="records")

    @staticmethod
    def _safe_val(v: Any) -> Any:
        """Convert numpy/pandas scalars to native Python types."""
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return float(v)
        return v
