from __future__ import annotations

import math
from typing import Final

from investlab.profit_taking.calculator_models import (
    CalculatorEvent,
    CalculatorEventType,
    CalculatorSummary,
    CalculatorValidationError,
    DailyState,
)

_TOLERANCE: Final = 1e-10
_XIRR_MAX_RATE: Final = 1_000_000_000_000.0
_XIRR_MAX_ITERATIONS: Final = 256
_XIRR_NPV_TOLERANCE: Final = 1e-12
_XIRR_RATE_TOLERANCE: Final = 1e-12


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
        (state.date, -state.external_contribution)
        for state in states
        if state.external_contribution > 0
    ]
    cashflows.append((states[-1].date, terminal_assets))
    origin = cashflows[0][0]

    def net_present_value(rate: float) -> float:
        return sum(
            amount / (1.0 + rate) ** ((flow_date - origin).days / 365.25)
            for flow_date, amount in cashflows
        )

    low = -0.9999
    high = 10.0
    npv_low = net_present_value(low)
    npv_high = net_present_value(high)
    if not math.isfinite(npv_low) or not math.isfinite(npv_high):
        return None
    for exponent in range(5, 13):
        if npv_low * npv_high <= 0:
            break
        candidate = -(1.0 - 10.0**-exponent)
        candidate_npv = net_present_value(candidate)
        if not math.isfinite(candidate_npv):
            break
        low, npv_low = candidate, candidate_npv
    while npv_low * npv_high > 0 and high < _XIRR_MAX_RATE:
        high = min(high * 2.0, _XIRR_MAX_RATE)
        npv_high = net_present_value(high)
        if not math.isfinite(npv_high):
            return None
    if npv_low * npv_high > 0:
        return None
    for _ in range(_XIRR_MAX_ITERATIONS):
        middle = (low + high) / 2.0
        npv_middle = net_present_value(middle)
        if not math.isfinite(npv_middle):
            return None
        if abs(npv_middle) < _XIRR_NPV_TOLERANCE or high - low <= (
            _XIRR_RATE_TOLERANCE * max(1.0, abs(middle))
        ):
            return middle
        if npv_low * npv_middle < 0:
            high = middle
        else:
            low = middle
            npv_low = npv_middle
    return None
