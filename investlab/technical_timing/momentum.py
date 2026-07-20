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
)
from investlab.technical_timing.models import IndicatorSignal


def _signal(buy: pd.Series, sell: pd.Series) -> IndicatorSignal:
    return IndicatorSignal("momentum", buy.fillna(False), sell.fillna(False))


def mom(frame: pd.DataFrame) -> IndicatorSignal:
    line = frame["close"] - frame["close"].shift(10)
    return _signal(line > 0, line < 0)


def bias(frame: pd.DataFrame) -> IndicatorSignal:
    line = (
        safe_div(frame["close"] - ma(frame["close"], 26), ma(frame["close"], 26))
        * 100.0
    )
    return _signal(line > 5.0, line < -5.0)


def rsi(frame: pd.DataFrame) -> IndicatorSignal:
    delta = frame["close"].diff()
    up = delta.clip(lower=0.0)
    down = (-delta).clip(lower=0.0)
    line = 100.0 * safe_div(ema(up, 14), ema(up, 14) + ema(down, 14))
    return _signal(crosses_above(line, 30.0), crosses_below(line, 70.0))


def roc(frame: pd.DataFrame) -> IndicatorSignal:
    line = 100.0 * safe_div(
        frame["close"] - frame["close"].shift(20), frame["close"].shift(20)
    )
    return _signal(line > 0, line < 0)


def kdj(frame: pd.DataFrame) -> IndicatorSignal:
    low = rolling_min(frame["low"], 9)
    high = rolling_max(frame["high"], 9)
    rsv = 100.0 * safe_div(frame["close"] - low, high - low)
    k = ema(rsv, 3)
    d = ma(k, 3)
    return _signal((d < 20.0) & crosses_above(k, d), (d > 80.0) & crosses_below(k, d))


def wr(frame: pd.DataFrame) -> IndicatorSignal:
    high = rolling_max(frame["high"], 6)
    low = rolling_min(frame["low"], 6)
    line = -100.0 * safe_div(high - frame["close"], high - low)
    return _signal(crosses_below(line, -80.0), crosses_above(line, -20.0))


def cci(frame: pd.DataFrame) -> IndicatorSignal:
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    mean = ma(typical, 14)
    deviation = (typical - mean).abs().rolling(14, min_periods=14).mean()
    line = safe_div(typical - mean, 0.015 * deviation)
    return _signal(line > 100.0, line < -100.0)


def cmo(frame: pd.DataFrame) -> IndicatorSignal:
    delta = frame["close"].diff()
    up = delta.clip(lower=0.0).rolling(25, min_periods=25).sum()
    down = (-delta.clip(upper=0.0)).rolling(25, min_periods=25).sum()
    line = 100.0 * safe_div(up - down, up + down)
    return _signal(line > 0, line < 0)


def uo(frame: pd.DataFrame) -> IndicatorSignal:
    close = frame["close"]
    th = pd.concat([frame["high"], close.shift(1)], axis=1).max(axis=1)
    tl = pd.concat([frame["low"], close.shift(1)], axis=1).min(axis=1)
    tr = th - tl
    xr = close - tl
    avg7 = xr.rolling(7, min_periods=7).sum() / tr.rolling(7, min_periods=7).sum()
    avg14 = xr.rolling(14, min_periods=14).sum() / tr.rolling(14, min_periods=14).sum()
    avg28 = xr.rolling(28, min_periods=28).sum() / tr.rolling(28, min_periods=28).sum()
    line = 100.0 * (4.0 * avg7 + 2.0 * avg14 + avg28) / 7.0
    return _signal(crosses_above(line, 70.0), crosses_below(line, 50.0))


def trix(frame: pd.DataFrame) -> IndicatorSignal:
    triple = ema(ema(ema(frame["close"], 12), 12), 12)
    line = triple.pct_change()
    trigger = ma(line, 20)
    return _signal(crosses_above(line, trigger), crosses_below(line, trigger))


def pos(frame: pd.DataFrame) -> IndicatorSignal:
    pc = frame["close"].pct_change(20)
    line = 100.0 * safe_div(
        pc - rolling_min(pc, 20), rolling_max(pc, 20) - rolling_min(pc, 20)
    )
    return _signal(crosses_above(line, 80.0), crosses_below(line, 20.0))
