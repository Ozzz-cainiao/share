from __future__ import annotations

import math
from typing import Final

import pandas as pd  # noqa: PANDAS_OK

from investlab.profit_taking.calculator_models import (
    CalculatorEvent,
    CalculatorEventType,
    CalculatorSummary,
    CalculatorValidationError,
    DailyState,
)
from investlab.utils import xirr

_TOLERANCE: Final = 1e-10


def contribution_neutral_nav(
    states: tuple[DailyState, ...],
) -> tuple[float, ...]:
    _validate_states(states)
    nav = [1.0]
    previous_assets = states[0].total_assets
    for state in states[1:]:
        pre_flow_assets = state.total_assets - state.external_contribution
        if previous_assets <= 0:
            raise CalculatorValidationError(
                "total_assets",
                "positive pre-flow assets require positive prior assets",
            )
        nav.append(nav[-1] * pre_flow_assets / previous_assets)
        previous_assets = state.total_assets
    return tuple(nav)


def compute_calculator_summary(
    states: tuple[DailyState, ...],
    events: tuple[CalculatorEvent, ...],
) -> CalculatorSummary:
    nav = contribution_neutral_nav(states)
    external_invested = sum(state.external_contribution for state in states)
    if external_invested <= 0:
        raise CalculatorValidationError(
            "external_contribution",
            "must contain a positive investor cash flow",
        )
    final = states[-1]
    total_profit = final.total_assets - external_invested
    xirr_value = _external_xirr(states, final.total_assets)
    peak = nav[0]
    maximum_drawdown = 0.0
    for value in nav[1:]:
        peak = max(peak, value)
        maximum_drawdown = min(maximum_drawdown, value / peak - 1.0)
    return CalculatorSummary(
        scheduled_invested=sum(state.scheduled_contribution for state in states),
        external_invested=external_invested,
        ending_holdings=final.holding_value,
        reusable_pool=final.reusable_pool,
        reserve=final.reserve,
        total_assets=final.total_assets,
        total_profit=total_profit,
        cumulative_return=total_profit / external_invested,
        xirr=xirr_value,
        maximum_drawdown=maximum_drawdown,
        time_in_market=sum(state.shares > 0 for state in states) / len(states),
        stop_count=sum(
            event.event_type is CalculatorEventType.SALE for event in events
        ),
    )


def _validate_states(states: tuple[DailyState, ...]) -> None:
    if not states:
        raise CalculatorValidationError(
            "daily_states",
            "must contain at least one observation",
        )
    for previous, current in zip(states, states[1:]):
        if current.date <= previous.date:
            raise CalculatorValidationError(
                "daily_states",
                "dates must be strictly increasing",
            )
    for state in states:
        if not math.isclose(
            state.scheduled_contribution,
            state.external_contribution + state.pool_contribution,
            rel_tol=_TOLERANCE,
            abs_tol=_TOLERANCE,
        ):
            raise CalculatorValidationError(
                "scheduled_contribution",
                "must equal external plus pool funding",
            )
        if not math.isclose(
            state.total_assets,
            state.holding_value + state.reusable_pool + state.reserve,
            rel_tol=_TOLERANCE,
            abs_tol=_TOLERANCE,
        ):
            raise CalculatorValidationError(
                "total_assets",
                "must equal holdings plus both cash balances",
            )


def _external_xirr(
    states: tuple[DailyState, ...],
    terminal_assets: float,
) -> float | None:
    if states[0].date == states[-1].date:
        return None
    cashflows = [
        (pd.Timestamp(state.date), -state.external_contribution)
        for state in states
        if state.external_contribution > 0
    ]
    cashflows.append((pd.Timestamp(states[-1].date), terminal_assets))
    value = xirr(cashflows)
    return value if math.isfinite(value) else None
