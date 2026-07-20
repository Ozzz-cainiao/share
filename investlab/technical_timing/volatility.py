from __future__ import annotations

import pandas as pd  # noqa: PANDAS_OK

from investlab.technical_timing.math import (
    crosses_above,
    crosses_below,
    ema,
    ma,
    rolling_max,
    rolling_min,
    safe_div,
    true_range,
)
from investlab.technical_timing.models import IndicatorSignal


def _signal(buy: pd.Series, sell: pd.Series) -> IndicatorSignal:
    return IndicatorSignal("volatility", buy.fillna(False), sell.fillna(False))


def atr_kc(frame: pd.DataFrame) -> IndicatorSignal:
    mid = ma(frame["close"], 14)
    atr = ema(true_range(frame), 14)
    return _channel_signal(frame["close"], mid + 2.0 * atr, mid - 2.0 * atr)


def bbands(frame: pd.DataFrame) -> IndicatorSignal:
    mid = ma(frame["close"], 20)
    width = frame["close"].rolling(20, min_periods=20).std()
    return _channel_signal(frame["close"], mid + 2.0 * width, mid - 2.0 * width)


def dc(frame: pd.DataFrame) -> IndicatorSignal:
    upper = rolling_max(frame["high"], 20).shift(1)
    lower = rolling_min(frame["low"], 20).shift(1)
    return _channel_signal(frame["close"], upper, lower)


def accbands(frame: pd.DataFrame) -> IndicatorSignal:
    ratio = safe_div(frame["high"] - frame["low"], frame["high"] + frame["low"])
    upper = ma(frame["high"] * (1.0 + 4.0 * ratio), 20)
    lower = ma(frame["low"] * (1.0 - 4.0 * ratio), 20)
    return _channel_signal(frame["close"], upper, lower)


def massi(frame: pd.DataFrame) -> IndicatorSignal:
    width = frame["high"] - frame["low"]
    line = (
        safe_div(ema(width, 9), ema(ema(width, 9), 9)).rolling(25, min_periods=25).sum()
    )
    trigger = crosses_below(line, 26.5) & (
        line.shift(1).rolling(20, min_periods=1).max() > 27.0
    )
    slope = frame["close"] - frame["close"].shift(9)
    return _signal(trigger & (slope < 0), trigger & (slope > 0))


def rvi(frame: pd.DataFrame) -> IndicatorSignal:
    close = frame["close"]
    std = close.rolling(14, min_periods=14).std()
    up = ema(std.where(close > close.shift(1), 0.0), 14)
    down = ema(std.where(close < close.shift(1), 0.0), 14)
    line = 100.0 * safe_div(up, up + down)
    return _signal(crosses_below(line, 30.0), crosses_above(line, 70.0))


def udvd(frame: pd.DataFrame) -> IndicatorSignal:
    up = safe_div(frame["high"] - frame["open"], frame["open"])
    down = safe_div(frame["open"] - frame["low"], frame["open"])
    line = ma(up - down, 20)
    return _signal(line > 0, line < 0)


def _channel_signal(
    close: pd.Series, upper: pd.Series, lower: pd.Series
) -> IndicatorSignal:
    return _signal(crosses_above(close, upper), crosses_below(close, lower))
