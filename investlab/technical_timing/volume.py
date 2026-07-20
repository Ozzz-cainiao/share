from __future__ import annotations

import pandas as pd  # noqa: PANDAS_OK

from investlab.technical_timing.math import (
    crosses_above,
    crosses_below,
    ema,
    ma,
    safe_div,
)
from investlab.technical_timing.models import IndicatorSignal


def _signal(buy: pd.Series, sell: pd.Series) -> IndicatorSignal:
    return IndicatorSignal("volume", buy.fillna(False), sell.fillna(False))


def ad(frame: pd.DataFrame) -> IndicatorSignal:
    high_low = (frame["high"] - frame["low"]).replace(0, pd.NA)
    money_flow = (
        ((frame["close"] - frame["low"]) - (frame["high"] - frame["close"]))
        * frame["volume"]
        / high_low
    )
    line = money_flow.fillna(0.0).cumsum()
    adosc = ema(line, 3) - ema(line, 10)
    trend = frame["close"] > ma(frame["close"], 90)
    return _signal((adosc > 0) & trend, (adosc < 0) & ~trend)


def obv(frame: pd.DataFrame) -> IndicatorSignal:
    signed = frame["volume"].where(
        frame["close"] > frame["close"].shift(1), -frame["volume"]
    )
    signed = signed.where(frame["close"] != frame["close"].shift(1), 0.0)
    line = signed.fillna(0.0).cumsum()
    histogram = ma(line, 10) - ma(line, 20)
    return _signal(histogram > 0, histogram < 0)


def mfi(frame: pd.DataFrame) -> IndicatorSignal:
    typical = (frame["high"] + frame["low"] + frame["close"]) / 3.0
    money = typical * frame["volume"]
    positive = (
        money.where(typical > typical.shift(1), 0.0).rolling(14, min_periods=14).sum()
    )
    negative = (
        money.where(typical <= typical.shift(1), 0.0).rolling(14, min_periods=14).sum()
    )
    line = 100.0 - 100.0 / (1.0 + safe_div(positive, negative))
    return _signal(crosses_above(line, 20.0), crosses_below(line, 80.0))


def eom(frame: pd.DataFrame) -> IndicatorSignal:
    midpoint = (frame["high"] + frame["low"]) / 2.0
    move = midpoint - midpoint.shift(1)
    ratio = safe_div(frame["volume"] / 10_000_000.0, frame["high"] - frame["low"])
    line = ma(safe_div(move, ratio), 20)
    return _signal(line > 0, line < 0)


def maamt(frame: pd.DataFrame) -> IndicatorSignal:
    line = ma(frame["volume"], 30)
    return _signal(
        crosses_above(frame["volume"], line), crosses_below(frame["volume"], line)
    )


def fi(frame: pd.DataFrame) -> IndicatorSignal:
    line = ema(frame["close"].diff() * frame["volume"], 13)
    return _signal(line > 0, line < 0)
