"""Look-ahead-safe momentum and structural-bull regime signals."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


def _n_month_return(series: pd.Series, months: int) -> float:
    """Return over trailing N months (skip most recent month)."""
    skip = 21
    lookback = months * 21
    if len(series) < lookback + skip + 1:
        return 0.0
    return float(series.iloc[-skip - 1] / series.iloc[-lookback - skip - 1] - 1.0)


def momentum_score(price_history: pd.DataFrame) -> dict[str, float]:
    """12-1, 6-1, 3-1 weighted momentum score (0.5/0.3/0.2)."""
    if price_history.empty:
        return {}
    scores = {}
    for col in price_history.columns:
        r12 = _n_month_return(price_history[col], 12)
        r6 = _n_month_return(price_history[col], 6)
        r3 = _n_month_return(price_history[col], 3)
        scores[col] = 0.5 * r12 + 0.3 * r6 + 0.2 * r3
    return scores


def momentum_rank_target(
    price_history: pd.DataFrame,
    vol_lookback: int = 63,
) -> dict[str, float]:
    """Volatility-scaled momentum rank → 60/30/10 target weights."""
    raw = momentum_score(price_history)
    if not raw:
        return {}

    # Volatility scaling
    vols = {}
    for col in price_history.columns:
        rets = price_history[col].pct_change().dropna().tail(vol_lookback)
        vols[col] = float(rets.std()) if len(rets) > 5 and rets.std() > 1e-12 else 1.0

    scaled = {k: raw[k] / vols[k] for k in raw}
    ranked = sorted(scaled.items(), key=lambda x: x[1], reverse=True)
    n = len(ranked)
    if n == 0:
        return {}

    target_map = {0: 0.60, 1: 0.30, 2: 0.10}
    result = {}
    for i, (k, _) in enumerate(ranked):
        result[k] = target_map.get(i, 0.0)
    return result


@dataclass
class RegimeSignal:
    """Monthly regime classification known at prior month-end."""
    is_structural_bull: bool = False
    is_uptrend: bool = False
    uptrend_assets: set[str] = None
    dispersion_above_median: bool = False
    raw_scores: dict[str, float] = None
    rank_targets: dict[str, float] = None

    def __post_init__(self):
        if self.uptrend_assets is None:
            self.uptrend_assets = set()
        if self.raw_scores is None:
            self.raw_scores = {}
        if self.rank_targets is None:
            self.rank_targets = {}


def classify_regime(
    price_history: pd.DataFrame,
    sma_fast: int = 60,
    sma_slow: int = 200,
    dispersion_window: int = 126,
    dispersion_median_window: int = 756,
) -> RegimeSignal:
    """Classify regime at month-end using only data available at that point."""
    if price_history.empty or len(price_history) < sma_slow:
        return RegimeSignal()

    # Equal-weight composite
    composite = price_history.mean(axis=1)

    # Uptrend: composite > 200-day SMA AND 60-day SMA rising
    above_slow = composite.iloc[-1] > composite.rolling(sma_slow).mean().iloc[-1]
    sma_fast_series = composite.rolling(sma_fast).mean()
    fast_rising = len(sma_fast_series) >= 21 and sma_fast_series.iloc[-1] > sma_fast_series.iloc[-21]

    is_uptrend = above_slow and fast_rising

    # Which assets are individually in uptrend
    uptrend_assets = set()
    for col in price_history.columns:
        s = price_history[col]
        if len(s) >= sma_slow:
            if s.iloc[-1] > s.rolling(sma_slow).mean().iloc[-1]:
                uptrend_assets.add(col)

    # Cross-index dispersion: std of trailing returns
    trailing_rets = {}
    for col in price_history.columns:
        if len(price_history[col]) >= dispersion_window + 1:
            trailing_rets[col] = float(
                price_history[col].iloc[-1] / price_history[col].iloc[-dispersion_window - 1] - 1.0
            )
    dispersion = float(np.std(list(trailing_rets.values()))) if trailing_rets else 0.0

    # Rolling median dispersion (shifted 1 session)
    if len(composite) >= dispersion_median_window + dispersion_window + 2:
        rolling_disp = []
        for i in range(dispersion_median_window):
            end_idx = -2 - i  # shift 1 session back
            start_idx = end_idx - dispersion_window
            if start_idx < -len(composite):
                break
            rets_i = []
            for col in price_history.columns:
                if abs(start_idx) <= len(price_history[col]) and abs(end_idx) <= len(price_history[col]):
                    rets_i.append(float(
                        price_history[col].iloc[end_idx] / price_history[col].iloc[start_idx] - 1.0
                    ))
            if rets_i:
                rolling_disp.append(float(np.std(rets_i)))
        median_disp = float(np.median(rolling_disp)) if rolling_disp else dispersion + 1
    else:
        median_disp = dispersion + 1

    dispersion_above = dispersion > median_disp

    # Structural bull: uptrend AND dispersion above median
    is_structural_bull = is_uptrend and dispersion_above

    scores = momentum_score(price_history)
    rank_targets = momentum_rank_target(price_history)

    return RegimeSignal(
        is_structural_bull=is_structural_bull,
        is_uptrend=is_uptrend,
        uptrend_assets=uptrend_assets,
        dispersion_above_median=dispersion_above,
        raw_scores=scores,
        rank_targets=rank_targets,
    )
