from __future__ import annotations

import numpy as np
import pandas as pd  # noqa: PANDAS_OK


def ma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def rolling_max(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).max()


def rolling_min(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=window).min()


def safe_div(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    clean = denominator.replace(0, np.nan)
    return numerator / clean


def crosses_above(left: pd.Series, right: pd.Series | float) -> pd.Series:
    right_series = _as_series(right, left.index)
    return (left > right_series) & (left.shift(1) <= right_series.shift(1))


def crosses_below(left: pd.Series, right: pd.Series | float) -> pd.Series:
    right_series = _as_series(right, left.index)
    return (left < right_series) & (left.shift(1) >= right_series.shift(1))


def true_range(frame: pd.DataFrame) -> pd.Series:
    high = frame["high"]
    low = frame["low"]
    previous_close = frame["close"].shift(1)
    ranges = pd.concat(
        [
            (high - low).abs(),
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    )
    return ranges.max(axis=1)


def _as_series(value: pd.Series | float, index: pd.Index) -> pd.Series:
    if isinstance(value, pd.Series):
        return value
    return pd.Series(value, index=index, dtype=float)
