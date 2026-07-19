from __future__ import annotations

import math
from typing import Final

import pandas as pd  # noqa: PANDAS_OK

from investlab.profit_taking.simple_backtest import (
    SimpleBacktestConfig,
    SimpleBacktestResult,
    SimpleDailyRow,
    SimpleProfitTake,
    SimpleSummary,
    _reached_target,
    _validated_prices,
)

TRAILING_DRAWDOWN: Final = 0.10


def run_drawdown_backtest(
    prices: pd.Series,
    config: SimpleBacktestConfig,
) -> SimpleBacktestResult:
    selected = _validated_prices(prices, config.start_date)
    shares = 0.0
    cycle_invested = 0.0
    reserve_pool = 0.0
    total_invested = 0.0
    contribution_count = 0
    previous_month: tuple[int, int] | None = None
    drawdown_armed = False
    drawdown_peak = 0.0
    rows: list[SimpleDailyRow] = []
    profit_takes: list[SimpleProfitTake] = []

    for timestamp, raw_close in selected.items():
        current_date = timestamp.date()
        close = float(raw_close)
        holding_before_flow = shares * close
        if (
            not drawdown_armed
            and shares > 0
            and _reached_target(
                holding_before_flow,
                cycle_invested,
                config.target_return,
            )
        ):
            drawdown_armed = True
            drawdown_peak = close
        elif drawdown_armed:
            drawdown_peak = max(drawdown_peak, close)
            drawdown = close / drawdown_peak - 1.0
            reached_drawdown = drawdown <= -TRAILING_DRAWDOWN or math.isclose(
                drawdown,
                -TRAILING_DRAWDOWN,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            if reached_drawdown:
                proceeds = holding_before_flow
                profit_takes.append(
                    SimpleProfitTake(
                        sequence=len(profit_takes) + 1,
                        date=current_date,
                        close=close,
                        shares_sold=shares,
                        cycle_invested=cycle_invested,
                        proceeds=proceeds,
                        cycle_profit=proceeds - cycle_invested,
                        cycle_return=proceeds / cycle_invested - 1.0,
                    )
                )
                reserve_pool += proceeds
                shares = 0.0
                cycle_invested = 0.0
                drawdown_armed = False
                drawdown_peak = 0.0

        contribution = 0.0
        current_month = (current_date.year, current_date.month)
        if current_month != previous_month:
            contribution = config.monthly_contribution
            shares += contribution / close
            cycle_invested += contribution
            total_invested += contribution
            contribution_count += 1
            previous_month = current_month

        holding_value = shares * close
        rows.append(
            SimpleDailyRow(
                date=current_date,
                close=close,
                contribution=contribution,
                shares=shares,
                cycle_invested=cycle_invested,
                reserve_pool=reserve_pool,
                holding_value=holding_value,
                total_assets=reserve_pool + holding_value,
            )
        )

    final_row = rows[-1]
    total_profit = final_row.total_assets - total_invested
    summary = SimpleSummary(
        start_date=rows[0].date,
        end_date=final_row.date,
        trading_days=len(rows),
        contribution_count=contribution_count,
        total_invested=total_invested,
        reserve_pool=reserve_pool,
        current_holding_value=final_row.holding_value,
        total_assets=final_row.total_assets,
        total_profit=total_profit,
        total_return=total_profit / total_invested,
        profit_take_count=len(profit_takes),
    )
    return SimpleBacktestResult(
        config=config,
        daily_rows=tuple(rows),
        profit_takes=tuple(profit_takes),
        summary=summary,
    )
