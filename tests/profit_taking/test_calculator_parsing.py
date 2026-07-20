from __future__ import annotations

import pytest

from investlab.profit_taking.calculator_models import (
    CalculatorValidationError,
    PercentageKind,
    parse_percentage,
)


@pytest.mark.parametrize(
    ("kind", "raw", "expected"),
    [
        (PercentageKind.TARGET_RETURN, "0.1", 0.001),
        (PercentageKind.TARGET_RETURN, "500", 5.0),
        (PercentageKind.TRAILING_DRAWDOWN, "99.0", 0.99),
        (PercentageKind.SALE_FRACTION, "100", 1.0),
    ],
)
def test_percentage_parser_accepts_inclusive_boundaries(
    kind: PercentageKind,
    raw: str,
    expected: float,
) -> None:
    # Given: a user-facing percentage on an inclusive boundary.
    # When: it crosses the parser boundary.
    parsed = parse_percentage(kind, raw)

    # Then: it is converted exactly once to decimal form.
    assert parsed == expected


@pytest.mark.parametrize(
    ("kind", "raw"),
    [
        (PercentageKind.TARGET_RETURN, ""),
        (PercentageKind.TARGET_RETURN, "abc"),
        (PercentageKind.TARGET_RETURN, "NaN"),
        (PercentageKind.TARGET_RETURN, "Infinity"),
        (PercentageKind.TARGET_RETURN, "0"),
        (PercentageKind.TARGET_RETURN, "500.1"),
        (PercentageKind.TRAILING_DRAWDOWN, "99.1"),
        (PercentageKind.SALE_FRACTION, "-1"),
        (PercentageKind.SALE_FRACTION, "20.01"),
        ("target_return", "20"),
        (True, "20"),
    ],
)
def test_percentage_parser_rejects_malformed_or_out_of_range_input(
    kind: PercentageKind | str | bool,
    raw: str,
) -> None:
    # Given: malformed, non-finite, imprecise, or out-of-range pasted input.
    # When/Then: parsing fails before a row can be produced.
    with pytest.raises(CalculatorValidationError):
        parse_percentage(kind, raw)
