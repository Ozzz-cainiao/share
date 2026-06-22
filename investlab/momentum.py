from __future__ import annotations

import pandas as pd


def n_month_return(series: pd.Series, months: int) -> float:
    """Percentage return over last ~21*N trading days."""
    lookback = months * 21
    if len(series) < lookback + 1:
        return 0.0
    return float(series.iloc[-1] / series.iloc[-lookback - 1] - 1.0)


def sma_signal(price_history: pd.Series, lookback_months: int) -> bool:
    """True if last close >= N-month simple moving average."""
    window = lookback_months * 21
    if len(price_history) < window:
        return False
    sma = price_history.rolling(window=window).mean().iloc[-1]
    last_close = price_history.iloc[-1]
    return bool(last_close >= sma)


def relative_momentum_rank(
    price_history: pd.DataFrame, lookback_months: int
) -> dict[str, float]:
    """Return {asset: N-month return} sorted by return descending."""
    if price_history.empty:
        return {}
    result: dict[str, float] = {}
    for col in price_history.columns:
        result[col] = n_month_return(price_history[col], lookback_months)
    return dict(sorted(result.items(), key=lambda x: x[1], reverse=True))
