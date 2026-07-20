from __future__ import annotations

import numpy as np
import pandas as pd  # noqa: PANDAS_OK

from investlab.technical_timing.math import crosses_above, crosses_below, ema, ma
from investlab.technical_timing.models import IndicatorSignal


def _signal(category: str, buy: pd.Series, sell: pd.Series) -> IndicatorSignal:
    return IndicatorSignal(
        category=category, buy=buy.fillna(False), sell=sell.fillna(False)
    )


def sma(frame: pd.DataFrame) -> IndicatorSignal:
    short = ma(frame["close"], 5)
    long = ma(frame["close"], 20)
    return _signal("trend", crosses_above(short, long), crosses_below(short, long))


def ema_cross(frame: pd.DataFrame) -> IndicatorSignal:
    short = ema(frame["close"], 10)
    long = ema(frame["close"], 20)
    return _signal("trend", crosses_above(short, long), crosses_below(short, long))


def kama_cross(frame: pd.DataFrame) -> IndicatorSignal:
    close = frame["close"]
    short = _kama(close, 10)
    long = _kama(close, 20)
    return _signal("trend", crosses_above(short, long), crosses_below(short, long))


def macd(frame: pd.DataFrame) -> IndicatorSignal:
    diff = ema(frame["close"], 12) - ema(frame["close"], 26)
    dea = ema(diff, 9)
    hist = 2.0 * (diff - dea)
    return _signal("trend", hist > 0, hist < 0)


def aroon(frame: pd.DataFrame) -> IndicatorSignal:
    high = frame["high"]
    low = frame["low"]
    n = 20
    up = high.rolling(n, min_periods=n).apply(
        lambda x: 100.0 * (int(np.argmax(x)) + 1) / n
    )
    down = low.rolling(n, min_periods=n).apply(
        lambda x: 100.0 * (int(np.argmin(x)) + 1) / n
    )
    line = up - down
    return _signal(
        "trend",
        crosses_above(up, 70.0) & (line > 0),
        crosses_below(down, 70.0) & (line < 0),
    )


def adx(frame: pd.DataFrame) -> IndicatorSignal:
    high = frame["high"]
    low = frame["low"]
    close = frame["close"]
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0.0)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs(),
        ],
        axis=1,
    ).max(axis=1)
    tr_sum = tr.rolling(14, min_periods=14).sum()
    plus_di = 100.0 * plus_dm.rolling(14, min_periods=14).sum() / tr_sum
    minus_di = 100.0 * minus_dm.rolling(14, min_periods=14).sum() / tr_sum
    return _signal(
        "trend", crosses_above(plus_di, minus_di), crosses_below(plus_di, minus_di)
    )


def dpo(frame: pd.DataFrame) -> IndicatorSignal:
    close = frame["close"]
    line = close - ma(close, 20).shift(11)
    return _signal("trend", crosses_above(line, 0.0), crosses_below(line, 0.0))


def sar_proxy(frame: pd.DataFrame) -> IndicatorSignal:
    line = parabolic_sar(frame["high"], frame["low"], step=0.02, maximum=0.2)
    close = frame["close"]
    return _signal("trend", close > line, close < line)


def parabolic_sar(
    high: pd.Series, low: pd.Series, step: float = 0.02, maximum: float = 0.2
) -> pd.Series:
    if len(high) == 0:
        return pd.Series(dtype=float, index=high.index)
    sar_values: list[float] = [float(low.iloc[0])]
    rising = True
    acceleration = step
    extreme = float(high.iloc[0])
    previous_sar = float(low.iloc[0])
    for index in range(1, len(high)):
        current_high = float(high.iloc[index])
        current_low = float(low.iloc[index])
        sar = previous_sar + acceleration * (extreme - previous_sar)
        if rising:
            if current_low < sar:
                rising = False
                sar = extreme
                extreme = current_low
                acceleration = step
            else:
                sar = min(sar, float(low.iloc[index - 1]), current_low)
                if current_high > extreme:
                    extreme = current_high
                    acceleration = min(acceleration + step, maximum)
        else:
            if current_high > sar:
                rising = True
                sar = extreme
                extreme = current_high
                acceleration = step
            else:
                sar = max(sar, float(high.iloc[index - 1]), current_high)
                if current_low < extreme:
                    extreme = current_low
                    acceleration = min(acceleration + step, maximum)
        sar_values.append(sar)
        previous_sar = sar
    return pd.Series(sar_values, index=high.index, name="SAR")


def _kama(close: pd.Series, window: int) -> pd.Series:
    change = (close - close.shift(window)).abs()
    volatility = close.diff().abs().rolling(window, min_periods=window).sum()
    er = change / volatility.replace(0, np.nan)
    fast = 2.0 / 3.0
    slow = 2.0 / 31.0
    sc = (er * (fast - slow) + slow) ** 2
    values: list[float] = []
    previous = float(close.iloc[0])
    for price, factor in zip(close.to_numpy(), sc.fillna(0.0).to_numpy(), strict=True):
        previous = previous + float(factor) * (float(price) - previous)
        values.append(previous)
    return pd.Series(values, index=close.index)
