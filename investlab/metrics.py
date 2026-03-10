from __future__ import annotations

import math

import numpy as np

from investlab.models import AssetSpec, BacktestResult, StrategySummary
from investlab.utils import xirr


def summarize_result(
    asset: AssetSpec,
    result: BacktestResult,
    risk_free_rate: float = 0.02,
) -> StrategySummary:
    daily_returns = result.equity_curve.pct_change().dropna()
    ann_return = float(daily_returns.mean() * 252.0) if not daily_returns.empty else math.nan
    ann_vol = (
        float(daily_returns.std(ddof=0) * np.sqrt(252.0))
        if not daily_returns.empty
        else math.nan
    )
    sharpe = (
        (ann_return - risk_free_rate) / ann_vol
        if ann_vol and not math.isnan(ann_vol) and ann_vol > 1e-12
        else math.nan
    )

    span_days = (result.equity_curve.index[-1] - result.equity_curve.index[0]).days
    years = span_days / 365.25 if span_days > 0 else math.nan
    cagr = (
        (result.final_value / result.total_contribution) ** (1.0 / years) - 1.0
        if years and years > 0 and result.total_contribution > 0 and result.final_value > 0
        else math.nan
    )

    return StrategySummary(
        asset_key=asset.key,
        asset_name=asset.name,
        strategy_name=result.strategy_name,
        strategy_display_name=result.display_name,
        final_value=result.final_value,
        total_contribution=result.total_contribution,
        xirr=xirr(result.cashflows),
        cagr=cagr,
        max_drawdown=float(result.drawdown_curve.min()) if not result.drawdown_curve.empty else math.nan,
        ann_return=ann_return,
        ann_vol=ann_vol,
        sharpe=sharpe,
        avg_invest_ratio=result.avg_invest_ratio,
        trade_count=result.trade_count,
    )
