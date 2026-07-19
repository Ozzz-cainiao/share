from __future__ import annotations

import pandas as pd  # noqa: PANDAS_OK

from investlab.profit_taking.simple_backtest import (
    SimpleBacktestConfig,
    SimpleBacktestResult,
    SimpleDailyRow,
    SimpleSummary,
    _validated_prices,
)


def run_baseline_backtest(
    prices: pd.Series,
    config: SimpleBacktestConfig,
) -> SimpleBacktestResult:
    selected = _validated_prices(prices, config.start_date)
    shares = 0.0
    total_invested = 0.0
    contribution_count = 0
    previous_month: tuple[int, int] | None = None
    rows: list[SimpleDailyRow] = []

    for timestamp, raw_close in selected.items():
        current_date = timestamp.date()
        close = float(raw_close)
        contribution = 0.0
        current_month = (current_date.year, current_date.month)
        if current_month != previous_month:
            contribution = config.monthly_contribution
            shares += contribution / close
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
                cycle_invested=total_invested,
                reserve_pool=0.0,
                holding_value=holding_value,
                total_assets=holding_value,
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
        reserve_pool=0.0,
        current_holding_value=final_row.holding_value,
        total_assets=final_row.total_assets,
        total_profit=total_profit,
        total_return=total_profit / total_invested,
        profit_take_count=0,
    )
    return SimpleBacktestResult(
        config=config,
        daily_rows=tuple(rows),
        profit_takes=(),
        summary=summary,
    )
