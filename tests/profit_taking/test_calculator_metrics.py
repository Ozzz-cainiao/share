from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from investlab.profit_taking.calculator_metrics import (
    compute_calculator_summary,
    contribution_neutral_nav,
)
from investlab.profit_taking.calculator_models import (
    Cadence,
    CalculatorEvent,
    CalculatorEventType,
    CalculatorValidationError,
    DailyState,
    StopFamily,
)
from tests.profit_taking.calculator_parity_builder import (
    build_parity_bytes,
    verify_parity_bytes,
)

_GOLDEN_PATH = Path(__file__).parent / "golden" / "calculator_parity.json"


def _state(
    day: str,
    *,
    scheduled: float,
    external: float,
    pool: float,
    holding: float,
    reusable: float = 0.0,
    reserve: float = 0.0,
) -> DailyState:
    return DailyState(
        date=date.fromisoformat(day),
        price=holding,
        scheduled_contribution=scheduled,
        external_contribution=external,
        pool_contribution=pool,
        shares=1.0,
        cycle_basis=holding,
        reusable_pool=reusable,
        reserve=reserve,
        holding_value=holding,
        total_assets=holding + reusable + reserve,
        nav=1.0,
    )


def test_summary_reconciles_pool_funded_and_external_flows() -> None:
    # Given: a later DCA is paid fully from reusable sale proceeds.
    states = (
        _state("2024-01-02", scheduled=100.0, external=100.0, pool=0.0, holding=100.0),
        _state(
            "2024-02-02",
            scheduled=100.0,
            external=0.0,
            pool=100.0,
            holding=100.0,
            reusable=20.0,
        ),
    )

    # When: calculator metrics are computed from daily ledger states.
    sale = CalculatorEvent(
        date(2024, 2, 2),
        CalculatorEventType.SALE,
        120.0,
        1.2,
        100.0,
    )
    summary = compute_calculator_summary(states, (sale,))

    # Then: scheduled and external cash remain distinct in returns and counts.
    assert summary.scheduled_invested == pytest.approx(200.0)
    assert summary.external_invested == pytest.approx(100.0)
    assert summary.cumulative_return == pytest.approx(0.2)


def test_xirr_uses_external_cash_only_and_known_annual_flow() -> None:
    # Given: ¥100 external cash grows to ¥110 over one 365.25-day solver year.
    states = (
        _state("2020-01-01", scheduled=100.0, external=100.0, pool=0.0, holding=100.0),
        _state("2020-12-31", scheduled=0.0, external=0.0, pool=0.0, holding=110.0),
    )

    # When: dated investor return is computed.
    summary = compute_calculator_summary(states, ())

    # Then: the known annual cash flow produces the solver's calendar-day result.
    assert summary.xirr == pytest.approx(1.1 ** (365.25 / 365) - 1.0)


def test_one_observation_has_no_invented_xirr() -> None:
    # Given: a valid single-observation investment window.
    states = (
        _state("2024-01-02", scheduled=100.0, external=100.0, pool=0.0, holding=100.0),
    )

    # When: its summary is computed.
    summary = compute_calculator_summary(states, ())

    # Then: zero-duration annual return is explicitly undefined.
    assert summary.xirr is None


def test_nav_and_drawdown_are_contribution_neutral() -> None:
    # Given: a large external deposit followed by a 50% market loss.
    states = (
        _state("2024-01-02", scheduled=100.0, external=100.0, pool=0.0, holding=100.0),
        _state(
            "2024-02-02",
            scheduled=1_000.0,
            external=1_000.0,
            pool=0.0,
            holding=1_100.0,
        ),
        _state("2024-03-01", scheduled=0.0, external=0.0, pool=0.0, holding=550.0),
    )

    # When: contribution-neutral performance is computed.
    nav = contribution_neutral_nav(states)
    summary = compute_calculator_summary(states, ())

    # Then: nominal deposits do not hide the actual drawdown.
    assert nav == pytest.approx((1.0, 1.0, 0.5))
    assert summary.maximum_drawdown == pytest.approx(-0.5)


def test_amount_and_price_scale_preserve_nav_drawdown_and_exposure() -> None:
    # Given: economically identical paths represented at two monetary scales.
    unit = (
        _state("2024-01-02", scheduled=100.0, external=100.0, pool=0.0, holding=100.0),
        _state("2024-01-03", scheduled=0.0, external=0.0, pool=0.0, holding=120.0),
        _state("2024-01-04", scheduled=0.0, external=0.0, pool=0.0, holding=90.0),
    )
    scaled = tuple(
        _state(
            state.date.isoformat(),
            scheduled=state.scheduled_contribution * 7,
            external=state.external_contribution * 7,
            pool=state.pool_contribution * 7,
            holding=state.holding_value * 7,
        )
        for state in unit
    )

    # When: both scales are summarized.
    unit_summary = compute_calculator_summary(unit, ())
    scaled_summary = compute_calculator_summary(scaled, ())

    # Then: normalized return, drawdown, and exposure do not depend on scale.
    assert contribution_neutral_nav(scaled) == pytest.approx(
        contribution_neutral_nav(unit)
    )
    assert scaled_summary.maximum_drawdown == pytest.approx(
        unit_summary.maximum_drawdown
    )
    assert scaled_summary.time_in_market == pytest.approx(unit_summary.time_in_market)


@pytest.mark.parametrize(
    "states",
    [
        (),
        (
            _state(
                "2024-01-03",
                scheduled=100.0,
                external=100.0,
                pool=0.0,
                holding=100.0,
            ),
            _state(
                "2024-01-02",
                scheduled=0.0,
                external=0.0,
                pool=0.0,
                holding=100.0,
            ),
        ),
        (
            _state(
                "2024-01-02",
                scheduled=100.0,
                external=90.0,
                pool=5.0,
                holding=100.0,
            ),
        ),
    ],
)
def test_malformed_states_fail_before_metrics_are_emitted(
    states: tuple[DailyState, ...],
) -> None:
    # Given: empty, stale-ordered, or unreconciled daily state.
    # When/Then: metrics reject it instead of producing misleading output.
    with pytest.raises(CalculatorValidationError):
        compute_calculator_summary(states, ())


def test_parity_corpus_covers_strategy_matrix_and_edge_contracts() -> None:
    # Given: the deterministic Python parity corpus.
    payload = json.loads(_GOLDEN_PATH.read_text(encoding="utf-8"))
    cases = payload["cases"]

    # When: coverage metadata is reduced to its required dimensions.
    matrix = {
        (case["config"]["cadence"], case["config"]["stop_family"])
        for case in cases
        if case["id"].startswith("matrix_")
    }
    tags = {tag for case in cases for tag in case["coverage"]}
    fractions = {
        case["config"]["sale_fraction"]
        for case in cases
        if case["config"]["sale_fraction"] is not None
    }
    recycle_values = {
        case["config"]["recycle_proceeds"]
        for case in cases
        if case["config"]["stop_family"] != StopFamily.NONE
    }

    # Then: all cross-runtime behavior classes are represented.
    assert matrix == {
        (cadence.value, stop.value) for cadence in Cadence for stop in StopFamily
    }
    assert {"exact_threshold", "near_threshold", "same_day", "repeated_cycles"} <= tags
    assert fractions == {0.01, 0.5, 1.0}
    assert recycle_values == {False, True}


def test_parity_corpus_replays_python_engine_and_metrics_exactly() -> None:
    # Given: serialized requests, prices, daily states, events, and summaries.
    payload = _GOLDEN_PATH.read_bytes()

    # When/Then: every serialized field matches a canonical Python replay.
    verify_parity_bytes(payload)


@pytest.mark.parametrize(
    ("section", "field"),
    [("daily_states", "cycle_basis"), ("events", "amount")],
)
def test_parity_replay_rejects_tampered_full_ledger_field(
    section: str,
    field: str,
) -> None:
    # Given: a previously unchecked state or event field is tampered.
    payload = json.loads(_GOLDEN_PATH.read_bytes())
    exact_case = next(
        case for case in payload["cases"] if case["id"] == "edge_exact_threshold"
    )
    exact_case[section][0][field] += 1.0

    # When/Then: full-ledger replay rejects the mutation.
    with pytest.raises(AssertionError):
        verify_parity_bytes(json.dumps(payload).encode())


def test_parity_corpus_builder_is_byte_identical() -> None:
    # Given: explicit deterministic configs and prices in the Python builder.
    # When: the corpus is regenerated through run_calculator.
    regenerated = build_parity_bytes()

    # Then: canonical output is byte-identical to the checked-in golden file.
    assert regenerated == _GOLDEN_PATH.read_bytes()
