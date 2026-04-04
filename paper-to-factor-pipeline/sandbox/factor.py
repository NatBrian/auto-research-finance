"""
Factor: PLACEHOLDER — awaiting agent implementation
ArXiv ID: null
Signal Type: null
Lookback: null
"""

import pandas as pd
import numpy as np


def generate_signals(data: pd.DataFrame) -> pd.Series:
    """
    Placeholder signal — returns random noise.
    This file will be replaced by the agent during factor-translate phase.

    Args:
        data: MultiIndex DataFrame (date, ticker) with OHLCV columns.

    Returns:
        pd.Series with same MultiIndex — random signal for testing pipeline.
    """
    np.random.seed(42)
    signals = pd.Series(
        np.random.randn(len(data)),
        index=data.index,
        name="signal"
    )
    return signals
