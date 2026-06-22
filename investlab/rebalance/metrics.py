"""TWR-based portfolio metrics separated from investor cash-flow returns."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from investlab.rebalance.models import MultiAssetBacktestResult
from investlab.utils import xirr


def compute_twr_metrics(
    result: MultiAssetBacktestResult,
    annual_cash_rate: float = 0.02,
) -> dict:
    """Compute time-weighted return metrics from NAV curve.

    TWR isolates manager performance from deposit/withdrawal timing.
    XIRR remains available separately for investor experience.
    """
    nav = result.nav_curve
    if len(nav) < 2:
        return _empty_metrics()

    daily_twr = nav.pct_change().dropna()
    n_days = len(daily_twr)
    years = n_days / 252.0 if n_days > 0 else math.nan

    # Geometric annualized return from NAV
    if nav.iloc[0] > 1e-12:
        total_twr = nav.iloc[-1] / nav.iloc[0] - 1.0
        ann_return = (1.0 + total_twr) ** (1.0 / years) - 1.0 if years > 0 else math.nan
    else:
        ann_return = math.nan

    # Volatility from daily TWR
    ann_vol = float(daily_twr.std(ddof=0) * np.sqrt(252.0)) if n_days > 1 else math.nan

    # Sharpe ratio
    sharpe = (
        (ann_return - annual_cash_rate) / ann_vol
        if ann_vol and ann_vol > 1e-12 and not math.isnan(ann_return)
        else math.nan
    )

    # Max drawdown from cumulative NAV
    cum_nav = (1.0 + daily_twr).cumprod()
    dd_series = cum_nav / cum_nav.cummax() - 1.0
    max_dd = float(dd_series.min()) if len(dd_series) > 0 else math.nan

    # Investor XIRR
    investor_xirr = xirr(result.cashflows)

    # Turnover stats
    avg_turnover = (
        float(result.turnover_series.mean())
        if result.turnover_series is not None and len(result.turnover_series) > 0
        else 0.0
    )

    return {
        "ann_return_twr": ann_return,
        "ann_vol_twr": ann_vol,
        "sharpe_twr": sharpe,
        "max_drawdown_twr": max_dd,
        "total_return_twr": float(total_twr) if not math.isnan(ann_return) else math.nan,
        "xirr_investor": investor_xirr,
        "avg_turnover": avg_turnover,
        "trade_count": result.trade_count,
        "final_value": result.final_value,
        "total_contribution": result.total_contribution,
        "initial_capital": result.initial_capital,
        "avg_cash_ratio": result.avg_cash_ratio,
        "n_days": n_days,
        "n_rebalances": len(result.rebalance_dates),
    }


def _empty_metrics() -> dict:
    nan = math.nan
    return {
        "ann_return_twr": nan, "ann_vol_twr": nan, "sharpe_twr": nan,
        "max_drawdown_twr": nan, "total_return_twr": nan,
        "xirr_investor": nan, "avg_turnover": 0.0,
        "trade_count": 0, "final_value": 0.0,
        "total_contribution": 0.0, "initial_capital": 0.0,
        "avg_cash_ratio": 0.0, "n_days": 0, "n_rebalances": 0,
    }
