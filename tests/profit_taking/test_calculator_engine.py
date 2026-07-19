from __future__ import annotations

from datetime import date

import pandas as pd  # noqa: PANDAS_OK
import pytest

from investlab.profit_taking.calculator_engine import run_calculator
from investlab.profit_taking.calculator_models import (
    Cadence,
    CalculatorEventType,
    CalculatorRequest,
    CalculatorResult,
    StopFamily,
    StrategyRowConfig,
)


def _row(
    *,
    stop_family: StopFamily = StopFamily.TARGET_RETURN,
    sale_fraction: float = 1.0,
    recycle: bool = False,
    cadence: Cadence = Cadence.MONTHLY,
) -> StrategyRowConfig:
    return StrategyRowConfig(
        name="方案",
        contribution_amount=100.0,
        cadence=cadence,
        stop_family=stop_family,
        target_return=None if stop_family is StopFamily.NONE else 0.2,
        trailing_drawdown=0.1 if stop_family is StopFamily.TRAILING_DRAWDOWN else None,
        sale_fraction=None if stop_family is StopFamily.NONE else sale_fraction,
        recycle_proceeds=recycle,
    )


def _run(
    values: list[tuple[str, float]],
    row: StrategyRowConfig,
) -> CalculatorResult:
    prices = pd.Series(
        [price for _, price in values],
        index=pd.to_datetime([day for day, _ in values]),
        dtype=float,
    )
    request = CalculatorRequest(
        date.fromisoformat(values[0][0]),
        date.fromisoformat(values[-1][0]),
        (row,),
    )
    return run_calculator(prices, request)[0]


@pytest.mark.parametrize(
    ("terminal_price", "expected_stops"),
    [(119.999999, 0), (120.0, 1), (120.000001, 1)],
)
def test_target_stop_uses_inclusive_threshold(
    terminal_price: float,
    expected_stops: int,
) -> None:
    # Given: one holding reaches just below, exactly, or above its 20% target.
    # When: the target strategy runs through the terminal close.
    result = _run([("2024-01-02", 100.0), ("2024-01-03", terminal_price)], _row())

    # Then: only the inclusive threshold and above execute a sale.
    assert result.summary.stop_count == expected_stops


@pytest.mark.parametrize(
    ("sale_fraction", "expected_shares", "expected_reserve"),
    [(0.01, 0.99, 1.2), (0.5, 0.5, 60.0), (1.0, 0.0, 120.0)],
)
def test_target_stop_supports_arbitrary_partial_and_full_sales(
    sale_fraction: float,
    expected_shares: float,
    expected_reserve: float,
) -> None:
    # Given: a target strategy configured for a chosen liquidation fraction.
    # When: the exact target is reached.
    result = _run(
        [("2024-01-02", 100.0), ("2024-01-03", 120.0)],
        _row(sale_fraction=sale_fraction),
    )

    # Then: proceeds and retained shares match the configured fraction.
    assert result.daily_states[-1].shares == pytest.approx(expected_shares)
    assert result.daily_states[-1].reserve == pytest.approx(expected_reserve)


def test_partial_sale_resets_retained_basis_to_market_value() -> None:
    # Given: a 50% sale at target followed by an unchanged close.
    result = _run(
        [("2024-01-02", 100.0), ("2024-01-03", 120.0), ("2024-01-04", 120.0)],
        _row(sale_fraction=0.5),
    )

    # When: the retained cycle is evaluated on the next day.
    sales = [
        event for event in result.events if event.event_type is CalculatorEventType.SALE
    ]

    # Then: resetting basis prevents an immediate repeated sale at the same price.
    assert len(sales) == 1
    assert result.daily_states[-1].cycle_basis == pytest.approx(60.0)


def test_same_day_sale_precedes_contribution_and_creates_new_cycle() -> None:
    # Given: an exact target occurs on February's scheduled contribution date.
    result = _run([("2024-01-02", 100.0), ("2024-02-01", 120.0)], _row())

    # When: same-close events are recorded.
    events = [
        event.event_type for event in result.events if event.date == date(2024, 2, 1)
    ]

    # Then: sale occurs before the new buy and the post-close basis is the new DCA.
    assert events == [CalculatorEventType.SALE, CalculatorEventType.CONTRIBUTION]
    assert result.daily_states[-1].shares == pytest.approx(100.0 / 120.0)
    assert result.daily_states[-1].cycle_basis == pytest.approx(100.0)


def test_recycled_proceeds_fund_only_scheduled_contribution() -> None:
    # Given: a full sale occurs on a scheduled contribution date with recycling enabled.
    result = _run([("2024-01-02", 100.0), ("2024-02-01", 120.0)], _row(recycle=True))

    # When: the same-day contribution is funded after the sale.
    final = result.daily_states[-1]

    # Then: exactly the scheduled amount moves from pool to holdings, with no external cash.
    assert final.pool_contribution == pytest.approx(100.0)
    assert final.external_contribution == pytest.approx(0.0)
    assert final.reusable_pool == pytest.approx(20.0)
    assert final.reserve == pytest.approx(0.0)


def test_non_recycled_reserve_never_funds_later_contribution() -> None:
    # Given: sale proceeds are configured for the non-reusable reserve.
    result = _run([("2024-01-02", 100.0), ("2024-02-01", 120.0)], _row())

    # When: the scheduled contribution follows the same-day sale.
    final = result.daily_states[-1]

    # Then: all contribution cash remains external and reserve stays untouched.
    assert final.external_contribution == pytest.approx(100.0)
    assert final.pool_contribution == pytest.approx(0.0)
    assert final.reserve == pytest.approx(120.0)


def test_trailing_stop_activates_then_sells_on_inclusive_peak_drawdown() -> None:
    # Given: the target activates at 120, a new peak reaches 130, then price falls 10%.
    result = _run(
        [
            ("2024-01-02", 100.0),
            ("2024-01-03", 120.0),
            ("2024-01-04", 130.0),
            ("2024-01-05", 117.0),
        ],
        _row(stop_family=StopFamily.TRAILING_DRAWDOWN),
    )

    # When: activation and trailing sale events are inspected.
    kinds = [event.event_type for event in result.events]

    # Then: target only arms, and the exact 10% drawdown later sells.
    assert kinds == [
        CalculatorEventType.CONTRIBUTION,
        CalculatorEventType.STOP_ACTIVATION,
        CalculatorEventType.SALE,
    ]


def test_trailing_stop_does_not_sell_before_activation() -> None:
    # Given: price peaks and falls 10% without ever reaching the target.
    result = _run(
        [("2024-01-02", 100.0), ("2024-01-03", 110.0), ("2024-01-04", 99.0)],
        _row(stop_family=StopFamily.TRAILING_DRAWDOWN),
    )

    # When/Then: no trailing stop is active and no sale occurs.
    assert result.summary.stop_count == 0


def test_trailing_partial_sale_resets_activation_for_repeated_cycle() -> None:
    # Given: a partial trailing sale, recovery to a new 20% cycle return, and another drawdown.
    result = _run(
        [
            ("2024-01-02", 100.0),
            ("2024-01-03", 120.0),
            ("2024-01-04", 108.0),
            ("2024-01-05", 129.6),
            ("2024-01-06", 116.64),
        ],
        _row(stop_family=StopFamily.TRAILING_DRAWDOWN, sale_fraction=0.5),
    )

    # When: sale events are counted after the second independently armed cycle.
    sales = [
        event for event in result.events if event.event_type is CalculatorEventType.SALE
    ]

    # Then: the trailing state reset permits exactly two separate cycles.
    assert len(sales) == 2


def test_no_stop_keeps_cash_balances_and_sale_count_zero() -> None:
    # Given: a daily no-stop strategy through a strong rally.
    result = _run(
        [("2024-01-02", 100.0), ("2024-01-03", 120.0)],
        _row(stop_family=StopFamily.NONE, cadence=Cadence.DAILY),
    )

    # When/Then: only contributions occur and all wealth remains invested.
    assert result.summary.stop_count == 0
    assert result.summary.reusable_pool == 0.0
    assert result.summary.reserve == 0.0


def test_every_daily_state_reconciles_contributions_and_assets() -> None:
    # Given: a recycled partial-sale path with multiple scheduled contributions.
    result = _run(
        [("2024-01-02", 100.0), ("2024-02-01", 120.0), ("2024-03-01", 130.0)],
        _row(sale_fraction=0.5, recycle=True),
    )

    # When/Then: every daily row satisfies both financial identities without rounding.
    for state in result.daily_states:
        assert state.scheduled_contribution == pytest.approx(
            state.pool_contribution + state.external_contribution
        )
        assert state.total_assets == pytest.approx(
            state.holding_value + state.reusable_pool + state.reserve
        )
