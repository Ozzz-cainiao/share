from __future__ import annotations

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

SELL_FRACTION: Final = 0.50


def run_partial_backtest(
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
    rows: list[SimpleDailyRow] = []
    profit_takes: list[SimpleProfitTake] = []

    for timestamp, raw_close in selected.items():
        current_date = timestamp.date()
        close = float(raw_close)
        holding_before_flow = shares * close
        if shares > 0 and _reached_target(
            holding_before_flow,
            cycle_invested,
            config.target_return,
        ):
            shares_sold = shares * SELL_FRACTION
            proceeds = shares_sold * close
            basis_sold = cycle_invested * SELL_FRACTION
            profit_takes.append(
                SimpleProfitTake(
                    sequence=len(profit_takes) + 1,
                    date=current_date,
                    close=close,
                    shares_sold=shares_sold,
                    cycle_invested=basis_sold,
                    proceeds=proceeds,
                    cycle_profit=proceeds - basis_sold,
                    cycle_return=proceeds / basis_sold - 1.0,
                )
            )
            reserve_pool += proceeds
            shares -= shares_sold
            cycle_invested = shares * close

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
