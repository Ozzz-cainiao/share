from __future__ import annotations

import math
from datetime import date
from typing import assert_never

import pandas as pd  # noqa: PANDAS_OK

from investlab.profit_taking.calculator_metrics import compute_calculator_summary
from investlab.profit_taking.calculator_models import (
    CalculatorEvent,
    CalculatorEventType,
    CalculatorRequest,
    CalculatorResult,
    DailyState,
    StopFamily,
    StrategyRowConfig,
)
from investlab.profit_taking.calculator_schedule import (
    contribution_dates,
    select_price_window,
)


def run_calculator(
    prices: pd.Series,
    request: CalculatorRequest,
) -> tuple[CalculatorResult, ...]:
    selected = select_price_window(prices, request.start_date, request.end_date)
    dates = tuple(timestamp.date() for timestamp in selected.index)
    return tuple(
        _run_strategy(selected, frozenset(contribution_dates(dates, row.cadence)), row)
        for row in request.rows
    )


def _run_strategy(
    selected: pd.Series,
    scheduled_dates: frozenset[date],
    config: StrategyRowConfig,
) -> CalculatorResult:
    shares = 0.0
    cycle_basis = 0.0
    reusable_pool = 0.0
    reserve = 0.0
    trailing_peak = 0.0
    trailing_armed = False
    nav = 1.0
    prior_assets = 0.0
    states: list[DailyState] = []
    events: list[CalculatorEvent] = []

    for timestamp, raw_price in selected.items():
        current_date = timestamp.date()
        price = float(raw_price)
        holding_before_flow = shares * price
        target = config.target_return or 0.0
        fraction = config.sale_fraction or 0.0
        target_reached = shares > 0 and _inclusive_at_least(
            holding_before_flow / cycle_basis - 1.0,
            target,
        )
        sell = False
        match config.stop_family:
            case StopFamily.NONE:
                pass
            case StopFamily.TARGET_RETURN:
                sell = target_reached
            case StopFamily.TRAILING_DRAWDOWN:
                if trailing_armed:
                    trailing_peak = max(trailing_peak, price)
                    drawdown = price / trailing_peak - 1.0
                    sell = _inclusive_at_most(
                        drawdown,
                        -(config.trailing_drawdown or 0.0),
                    )
                elif target_reached:
                    trailing_armed = True
                    trailing_peak = price
                    events.append(
                        CalculatorEvent(
                            current_date,
                            CalculatorEventType.STOP_ACTIVATION,
                            0.0,
                            0.0,
                            price,
                        )
                    )
            case unreachable:
                assert_never(unreachable)

        if sell:
            sold_shares = shares * fraction
            proceeds = sold_shares * price
            shares -= sold_shares
            cycle_basis = shares * price
            if config.recycle_proceeds:
                reusable_pool += proceeds
            else:
                reserve += proceeds
            trailing_armed = False
            trailing_peak = 0.0
            events.append(
                CalculatorEvent(
                    current_date,
                    CalculatorEventType.SALE,
                    proceeds,
                    sold_shares,
                    price,
                )
            )

        scheduled = (
            config.contribution_amount if current_date in scheduled_dates else 0.0
        )
        pool_funded = min(reusable_pool, scheduled)
        external = scheduled - pool_funded
        if scheduled > 0:
            reusable_pool -= pool_funded
            shares_bought = scheduled / price
            shares += shares_bought
            cycle_basis += scheduled
            events.append(
                CalculatorEvent(
                    current_date,
                    CalculatorEventType.CONTRIBUTION,
                    scheduled,
                    shares_bought,
                    price,
                )
            )

        holding_value = shares * price
        total_assets = holding_value + reusable_pool + reserve
        if prior_assets > 0:
            nav *= (total_assets - external) / prior_assets
        states.append(
            DailyState(
                date=current_date,
                price=price,
                scheduled_contribution=scheduled,
                external_contribution=external,
                pool_contribution=pool_funded,
                shares=shares,
                cycle_basis=cycle_basis,
                reusable_pool=reusable_pool,
                reserve=reserve,
                holding_value=holding_value,
                total_assets=total_assets,
                nav=nav,
            )
        )
        prior_assets = total_assets

    daily_states = tuple(states)
    event_rows = tuple(events)
    summary = compute_calculator_summary(daily_states, event_rows)
    return CalculatorResult(config, daily_states, event_rows, summary)


def _inclusive_at_least(value: float, threshold: float) -> bool:
    return value >= threshold or math.isclose(
        value,
        threshold,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def _inclusive_at_most(value: float, threshold: float) -> bool:
    return value <= threshold or math.isclose(
        value,
        threshold,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
