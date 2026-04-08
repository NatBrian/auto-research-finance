"""Sector mappings and exposure tracking for risk management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


# GICS sector names
GICS_SECTORS = [
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Healthcare",
    "Industrials",
    "Information Technology",
    "Materials",
    "Real Estate",
    "Utilities",
]

# Default sector mappings for common S&P 500 tickers
# This is a simplified mapping - in production, use a proper data source
DEFAULT_SECTOR_MAP: dict[str, str] = {
    # Information Technology
    "AAPL": "Information Technology",
    "MSFT": "Information Technology",
    "NVDA": "Information Technology",
    "GOOGL": "Communication Services",
    "META": "Communication Services",
    "CSCO": "Information Technology",
    "INTC": "Information Technology",
    "AMD": "Information Technology",
    "ORCL": "Information Technology",
    "CRM": "Information Technology",
    "IBM": "Information Technology",
    "QCOM": "Information Technology",
    "TXN": "Information Technology",
    "AVGO": "Information Technology",

    # Communication Services
    "DIS": "Communication Services",
    "NFLX": "Communication Services",
    "CMCSA": "Communication Services",
    "VZ": "Communication Services",
    "T": "Communication Services",
    "TMUS": "Communication Services",

    # Financials
    "JPM": "Financials",
    "BAC": "Financials",
    "WFC": "Financials",
    "GS": "Financials",
    "MS": "Financials",
    "BLK": "Financials",
    "SCHW": "Financials",
    "AXP": "Financials",
    "V": "Financials",
    "MA": "Financials",
    "C": "Financials",
    "USB": "Financials",
    "PNC": "Financials",

    # Healthcare
    "JNJ": "Healthcare",
    "UNH": "Healthcare",
    "PFE": "Healthcare",
    "ABT": "Healthcare",
    "MRK": "Healthcare",
    "TMO": "Healthcare",
    "LLY": "Healthcare",
    "ABBV": "Healthcare",
    "DHR": "Healthcare",
    "BMY": "Healthcare",
    "AMGN": "Healthcare",
    "MDT": "Healthcare",
    "GILD": "Healthcare",
    "CVS": "Healthcare",

    # Consumer Discretionary
    "AMZN": "Consumer Discretionary",
    "TSLA": "Consumer Discretionary",
    "HD": "Consumer Discretionary",
    "MCD": "Consumer Discretionary",
    "NKE": "Consumer Discretionary",
    "SBUX": "Consumer Discretionary",
    "LOW": "Consumer Discretionary",
    "TJX": "Consumer Discretionary",
    "BKNG": "Consumer Discretionary",

    # Consumer Staples
    "PG": "Consumer Staples",
    "KO": "Consumer Staples",
    "PEP": "Consumer Staples",
    "COST": "Consumer Staples",
    "WMT": "Consumer Staples",
    "PM": "Consumer Staples",
    "MO": "Consumer Staples",
    "MDLZ": "Consumer Staples",
    "CL": "Consumer Staples",
    "KMB": "Consumer Staples",

    # Energy
    "XOM": "Energy",
    "CVX": "Energy",
    "COP": "Energy",
    "SLB": "Energy",
    "EOG": "Energy",
    "PSX": "Energy",
    "VLO": "Energy",
    "MPC": "Energy",
    "OXY": "Energy",

    # Industrials
    "RTX": "Industrials",
    "BA": "Industrials",
    "CAT": "Industrials",
    "HON": "Industrials",
    "UPS": "Industrials",
    "GE": "Industrials",
    "MMM": "Industrials",
    "LMT": "Industrials",
    "DE": "Industrials",
    "EMR": "Industrials",
    "FDX": "Industrials",

    # Materials
    "LIN": "Materials",
    "APD": "Materials",
    "SHW": "Materials",
    "FCX": "Materials",
    "DOW": "Materials",
    "NEM": "Materials",
    "PPG": "Materials",

    # Real Estate
    "AMT": "Real Estate",
    "PLD": "Real Estate",
    "CCI": "Real Estate",
    "EQIX": "Real Estate",
    "SPG": "Real Estate",
    "PSA": "Real Estate",
    "O": "Real Estate",

    # Utilities
    "NEE": "Utilities",
    "DUK": "Utilities",
    "SO": "Utilities",
    "D": "Utilities",
    "EXC": "Utilities",
    "AEP": "Utilities",
    "SRE": "Utilities",
    "XEL": "Utilities",
    "PEG": "Utilities",
    "WEC": "Utilities",

    # Delisted/bankrupt
    "BBBY": "Consumer Discretionary",
}


class SectorMapper:
    """
    Manages sector mappings for portfolio risk analysis.
    """

    def __init__(
        self,
        sector_map: dict[str, str] | None = None,
        csv_path: str | Path | None = None,
    ):
        """
        Initialize sector mapper.

        Args:
            sector_map: Dictionary mapping ticker to sector.
            csv_path: Path to CSV file with sector mappings.
        """
        self._sector_map = DEFAULT_SECTOR_MAP.copy()

        if sector_map:
            self._sector_map.update(sector_map)

        if csv_path:
            self._load_from_csv(csv_path)

    def _load_from_csv(self, path: str | Path) -> None:
        """Load sector mappings from CSV file."""
        path = Path(path)
        if not path.exists():
            return

        df = pd.read_csv(path)
        if "Ticker" in df.columns and "Sector" in df.columns:
            for _, row in df.iterrows():
                self._sector_map[row["Ticker"]] = row["Sector"]

    def get_sector(self, ticker: str) -> str:
        """Get sector for a ticker."""
        return self._sector_map.get(ticker, "Unknown")

    def get_all_sectors(self) -> list[str]:
        """Get list of all unique sectors."""
        return sorted(set(self._sector_map.values()))

    def map_portfolio(
        self,
        weights: pd.Series,
    ) -> pd.Series:
        """
        Map portfolio weights to sector weights.

        Args:
            weights: Weight series indexed by ticker.

        Returns:
            Series of sector weights.
        """
        if isinstance(weights.index, pd.MultiIndex):
            # Take latest date
            latest_date = weights.index.get_level_values("date").max()
            weights = weights.xs(latest_date, level="date")

        sector_weights: dict[str, float] = {}
        for ticker, weight in weights.items():
            if pd.isna(weight):
                continue
            sector = self.get_sector(ticker)
            sector_weights[sector] = sector_weights.get(sector, 0.0) + abs(weight)

        return pd.Series(sector_weights, name="sector_weight")

    def sector_exposure_summary(
        self,
        weights: pd.Series,
    ) -> dict[str, Any]:
        """
        Compute detailed sector exposure summary.

        Args:
            weights: Weight series with MultiIndex (date, ticker).

        Returns:
            Dictionary with sector breakdown and concentration metrics.
        """
        sector_weights = self.map_portfolio(weights)

        if sector_weights.empty:
            return {
                "sectors": {},
                "top_sector": None,
                "top_sector_weight": 0.0,
                "num_sectors": 0,
                "herfindahl": 0.0,
            }

        # Sort by weight
        sector_weights = sector_weights.sort_values(ascending=False)

        # Herfindahl index (concentration)
        herfindahl = float((sector_weights ** 2).sum())

        return {
            "sectors": sector_weights.to_dict(),
            "top_sector": sector_weights.index[0],
            "top_sector_weight": float(sector_weights.iloc[0]),
            "num_sectors": len(sector_weights),
            "herfindahl": herfindahl,
        }

    def __getitem__(self, ticker: str) -> str:
        """Allow dict-like access: mapper['AAPL']."""
        return self.get_sector(ticker)

    def __contains__(self, ticker: str) -> bool:
        """Check if ticker is in the mapping."""
        return ticker in self._sector_map


# Default mapper instance
default_mapper = SectorMapper()