from __future__ import annotations

import json
import math
from datetime import date
from typing import Final

import pandas as pd  # noqa: PANDAS_OK

from investlab.profit_taking.calculator_engine import run_calculator
from investlab.profit_taking.calculator_metrics import (
    compute_calculator_summary,
    contribution_neutral_nav,
)
from investlab.profit_taking.calculator_models import (
    Cadence,
    CalculatorRequest,
    CalculatorResult,
    StopFamily,
    StrategyRowConfig,
)
from tests.profit_taking.calculator_parity_cases import (
    ParityCaseSpec,
    parity_case_specs,
)

_STATE_FIELDS: Final = (
    "price",
    "scheduled_contribution",
    "external_contribution",
    "pool_contribution",
    "shares",
    "cycle_basis",
    "reusable_pool",
    "reserve",
    "holding_value",
    "total_assets",
    "nav",
)
_EVENT_FIELDS: Final = ("amount", "shares", "price")
_SUMMARY_FIELDS: Final = (
    "scheduled_invested",
    "external_invested",
    "ending_holdings",
    "reusable_pool",
    "reserve",
    "total_assets",
    "total_profit",
    "cumulative_return",
    "maximum_drawdown",
    "time_in_market",
)


def build_parity_bytes() -> bytes:
    cases = []
    for spec in parity_case_specs():
        result = _run_spec(spec)
        nav = contribution_neutral_nav(result.daily_states)
        summary = compute_calculator_summary(result.daily_states, result.events)
        config = spec.config
        cases.append(
            {
                "actual_end": result.daily_states[-1].date.isoformat(),
                "actual_start": result.daily_states[0].date.isoformat(),
                "config": {
                    "cadence": config.cadence.value,
                    "contribution_amount": config.contribution_amount,
                    "name": config.name,
                    "recycle_proceeds": config.recycle_proceeds,
                    "sale_fraction": config.sale_fraction,
                    "stop_family": config.stop_family.value,
                    "target_return": config.target_return,
                    "trailing_drawdown": config.trailing_drawdown,
                },
                "coverage": list(spec.coverage),
                "daily_states": [
                    {
                        "cycle_basis": state.cycle_basis,
                        "date": state.date.isoformat(),
                        "external_contribution": state.external_contribution,
                        "holding_value": state.holding_value,
                        "nav": nav_value,
                        "pool_contribution": state.pool_contribution,
                        "price": state.price,
                        "reserve": state.reserve,
                        "reusable_pool": state.reusable_pool,
                        "scheduled_contribution": state.scheduled_contribution,
                        "shares": state.shares,
                        "total_assets": state.total_assets,
                    }
                    for state, nav_value in zip(
                        result.daily_states,
                        nav,
                        strict=True,
                    )
                ],
                "events": [
                    {
                        "amount": event.amount,
                        "date": event.date.isoformat(),
                        "event_type": event.event_type.value,
                        "price": event.price,
                        "shares": event.shares,
                    }
                    for event in result.events
                ],
                "id": spec.identifier,
                "prices": [{"close": close, "date": day} for day, close in spec.points],
                "requested_end": spec.requested_end.isoformat(),
                "requested_start": spec.requested_start.isoformat(),
                "summary": {
                    "cumulative_return": summary.cumulative_return,
                    "ending_holdings": summary.ending_holdings,
                    "external_invested": summary.external_invested,
                    "maximum_drawdown": summary.maximum_drawdown,
                    "reserve": summary.reserve,
                    "reusable_pool": summary.reusable_pool,
                    "scheduled_invested": summary.scheduled_invested,
                    "stop_count": summary.stop_count,
                    "time_in_market": summary.time_in_market,
                    "total_assets": summary.total_assets,
                    "total_profit": summary.total_profit,
                    "xirr": summary.xirr,
                },
            }
        )
    payload = {"cases": cases, "schema_version": 1}
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def verify_parity_bytes(payload: bytes) -> None:
    parsed = json.loads(payload)
    assert parsed["schema_version"] == 1
    for case in parsed["cases"]:
        config_data = case["config"]
        config = StrategyRowConfig(
            name=config_data["name"],
            contribution_amount=config_data["contribution_amount"],
            cadence=Cadence(config_data["cadence"]),
            stop_family=StopFamily(config_data["stop_family"]),
            target_return=config_data["target_return"],
            trailing_drawdown=config_data["trailing_drawdown"],
            sale_fraction=config_data["sale_fraction"],
            recycle_proceeds=config_data["recycle_proceeds"],
        )
        points = tuple((point["date"], point["close"]) for point in case["prices"])
        spec = ParityCaseSpec(
            case["id"],
            config,
            points,
            tuple(case["coverage"]),
            date.fromisoformat(case["requested_start"]),
            date.fromisoformat(case["requested_end"]),
        )
        result = _run_spec(spec)
        summary = compute_calculator_summary(result.daily_states, result.events)
        assert result.summary == summary
        assert result.daily_states[0].date.isoformat() == case["actual_start"]
        assert result.daily_states[-1].date.isoformat() == case["actual_end"]
        assert len(result.daily_states) == len(case["daily_states"])
        for actual, expected in zip(
            result.daily_states,
            case["daily_states"],
            strict=True,
        ):
            assert actual.date.isoformat() == expected["date"]
            for field in _STATE_FIELDS:
                assert _close(getattr(actual, field), expected[field])
        assert len(result.events) == len(case["events"])
        for actual, expected in zip(result.events, case["events"], strict=True):
            assert actual.date.isoformat() == expected["date"]
            assert actual.event_type.value == expected["event_type"]
            for field in _EVENT_FIELDS:
                assert _close(getattr(actual, field), expected[field])
        expected_summary = case["summary"]
        for field in _SUMMARY_FIELDS:
            assert _close(getattr(summary, field), expected_summary[field])
        assert summary.stop_count == expected_summary["stop_count"]
        if summary.xirr is None:
            assert expected_summary["xirr"] is None
        else:
            assert _close(summary.xirr, expected_summary["xirr"])


def _run_spec(spec: ParityCaseSpec) -> CalculatorResult:
    prices = pd.Series(
        [close for _, close in spec.points],
        index=pd.to_datetime([day for day, _ in spec.points]),
        dtype=float,
    )
    return run_calculator(
        prices,
        CalculatorRequest(
            spec.requested_start,
            spec.requested_end,
            (spec.config,),
        ),
    )[0]


def _close(actual: float, expected: float) -> bool:
    return math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
