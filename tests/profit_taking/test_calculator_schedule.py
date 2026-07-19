from __future__ import annotations

from datetime import date

import pandas as pd  # noqa: PANDAS_OK
import pytest

from investlab.profit_taking.calculator_models import (
    Cadence,
    CalculatorValidationError,
)
from investlab.profit_taking.calculator_schedule import (
    contribution_dates,
    select_price_window,
)


def _prices(dates: list[str]) -> pd.Series:
    return pd.Series(
        [100.0 + offset for offset in range(len(dates))],
        index=pd.to_datetime(dates),
        dtype=float,
    )


def test_select_price_window_resolves_non_trading_boundaries_inward() -> None:
    # Given: requested weekend boundaries around three trading observations.
    prices = _prices(["2024-01-08", "2024-01-10", "2024-01-12"])

    # When: the inclusive window is selected.
    selected = select_price_window(prices, date(2024, 1, 7), date(2024, 1, 13))

    # Then: actual coverage starts and ends at the inward trading observations.
    assert tuple(timestamp.date() for timestamp in selected.index) == (
        date(2024, 1, 8),
        date(2024, 1, 10),
        date(2024, 1, 12),
    )


def test_select_price_window_accepts_one_observation() -> None:
    # Given: a request whose inward boundaries resolve to one observation.
    prices = _prices(["2024-01-05", "2024-01-08"])

    # When: the narrow window is selected.
    selected = select_price_window(prices, date(2024, 1, 6), date(2024, 1, 8))

    # Then: the sole resolved date remains usable.
    assert tuple(timestamp.date() for timestamp in selected.index) == (
        date(2024, 1, 8),
    )


@pytest.mark.parametrize(
    ("cadence", "expected"),
    [
        (
            Cadence.DAILY,
            (
                "2023-12-29",
                "2024-01-02",
                "2024-01-08",
                "2024-01-15",
                "2024-02-01",
                "2024-04-01",
            ),
        ),
        (
            Cadence.WEEKLY,
            (
                "2023-12-29",
                "2024-01-02",
                "2024-01-08",
                "2024-01-15",
                "2024-02-01",
                "2024-04-01",
            ),
        ),
        (Cadence.BIWEEKLY, ("2023-12-29", "2024-01-15", "2024-02-01", "2024-04-01")),
        (Cadence.MONTHLY, ("2023-12-29", "2024-01-02", "2024-02-01", "2024-04-01")),
        (Cadence.QUARTERLY, ("2023-12-29", "2024-01-02", "2024-04-01")),
    ],
)
def test_contribution_dates_lock_all_five_cadences(
    cadence: Cadence,
    expected: tuple[str, ...],
) -> None:
    # Given: sparse trading dates spanning ISO weeks, months, and quarters.
    dates = tuple(
        timestamp.date()
        for timestamp in pd.to_datetime(
            [
                "2023-12-29",
                "2024-01-02",
                "2024-01-08",
                "2024-01-15",
                "2024-02-01",
                "2024-04-01",
            ]
        )
    )

    # When: scheduled dates are emitted for one cadence.
    scheduled = contribution_dates(dates, cadence)

    # Then: the first observation in every exact cadence bucket is selected.
    assert scheduled == tuple(date.fromisoformat(value) for value in expected)


@pytest.mark.parametrize(
    "prices",
    [
        pd.Series(dtype=float),
        pd.Series([100.0], index=["2024-01-02"]),
        pd.Series([100.0, 101.0], index=pd.to_datetime(["2024-01-03", "2024-01-02"])),
        pd.Series([100.0, 101.0], index=pd.to_datetime(["2024-01-02", "2024-01-02"])),
        pd.Series([0.0], index=pd.to_datetime(["2024-01-02"])),
    ],
)
def test_select_price_window_rejects_malformed_prices(prices: pd.Series) -> None:
    # Given: malformed input that cannot form a deterministic price window.
    # When/Then: selection fails at the boundary with a typed error.
    with pytest.raises(CalculatorValidationError, match="prices"):
        select_price_window(prices, date(2024, 1, 1), date(2024, 1, 31))


def test_select_price_window_rejects_empty_inward_coverage() -> None:
    # Given: valid prices entirely outside the requested range.
    prices = _prices(["2024-02-01"])

    # When/Then: inward resolution cannot invent an observation.
    with pytest.raises(CalculatorValidationError, match="price_window"):
        select_price_window(prices, date(2024, 1, 1), date(2024, 1, 31))
