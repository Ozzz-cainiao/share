from __future__ import annotations

import math
from dataclasses import FrozenInstanceError
from datetime import date

import pytest

from investlab.profit_taking.calculator_models import (
    Cadence,
    CalculatorEvent,
    CalculatorEventType,
    CalculatorRequest,
    CalculatorResult,
    CalculatorSummary,
    CalculatorValidationError,
    PercentageKind,
    StopFamily,
    StrategyRowConfig,
    parse_percentage,
)


def _row(
    name: str = "月投",
    *,
    cadence: Cadence = Cadence.MONTHLY,
    stop_family: StopFamily = StopFamily.NONE,
    target_return: float | None = None,
    trailing_drawdown: float | None = None,
    sale_fraction: float | None = None,
    recycle_proceeds: bool = False,
) -> StrategyRowConfig:
    return StrategyRowConfig(
        name=name,
        contribution_amount=1_000,
        cadence=cadence,
        stop_family=stop_family,
        target_return=target_return,
        trailing_drawdown=trailing_drawdown,
        sale_fraction=sale_fraction,
        recycle_proceeds=recycle_proceeds,
    )


def _target(
    name: str,
    fraction: float = 1.0,
    recycle: bool = False,
) -> StrategyRowConfig:
    return _row(
        name,
        stop_family=StopFamily.TARGET_RETURN,
        target_return=0.2,
        sale_fraction=fraction,
        recycle_proceeds=recycle,
    )


def _summary() -> CalculatorSummary:
    return CalculatorSummary(1_000, 1_000, 1_000, 0, 0, 1_000, 0, 0, None, 0, 1, 0)


def test_request_accepts_one_to_five_ordered_rows_with_duplicates() -> None:
    # Given: five ordered rows, including duplicate stop families.
    rows = (
        _row("日投", cadence=Cadence.DAILY),
        _target("目标一", 0.5),
        _target("目标二", recycle=True),
        _row(
            "回撤",
            cadence=Cadence.BIWEEKLY,
            stop_family=StopFamily.TRAILING_DRAWDOWN,
            target_return=0.2,
            trailing_drawdown=0.1,
            sale_fraction=1.0,
        ),
        _row("季度", cadence=Cadence.QUARTERLY),
    )

    # When: the calculator request is constructed.
    request = CalculatorRequest(date(2019, 1, 1), date(2024, 12, 31), rows)

    # Then: duplicates and row order are retained exactly.
    assert request.rows == rows


def test_request_rejects_mutable_rows_container_and_invalid_members() -> None:
    # Given: a mutable row container or a tuple containing a non-row value.
    row = _row()

    # When/Then: neither input crosses the request boundary.
    with pytest.raises(CalculatorValidationError, match="rows"):
        CalculatorRequest(date(2019, 1, 1), date(2020, 1, 1), [row])
    with pytest.raises(CalculatorValidationError, match="rows"):
        CalculatorRequest(date(2019, 1, 1), date(2020, 1, 1), (object(),))


@pytest.mark.parametrize(
    ("cadence", "stop_family"),
    [
        ("nonsense", StopFamily.NONE),
        (Cadence.MONTHLY, "nonsense"),
    ],
)
def test_row_rejects_raw_string_enum_fields(
    cadence: Cadence | str,
    stop_family: StopFamily | str,
) -> None:
    # Given: a raw string where an exact enum instance is required.
    # When/Then: row construction rejects it with a typed validation error.
    with pytest.raises(CalculatorValidationError):
        StrategyRowConfig("错误枚举", 1_000, cadence, stop_family)


def test_event_rejects_raw_string_event_type() -> None:
    # Given: an event whose enum field is a raw string.
    # When/Then: event construction rejects it at the boundary.
    with pytest.raises(CalculatorValidationError, match="event_type"):
        CalculatorEvent(date(2020, 1, 1), "sale", 1_000, 10, 100)


def test_request_and_result_do_not_retain_mutable_sequence_aliases() -> None:
    # Given: valid immutable records and mutable list aliases.
    row = _row()
    summary = _summary()

    # When/Then: mutable sequence aliases are rejected, not retained.
    with pytest.raises(CalculatorValidationError, match="rows"):
        CalculatorRequest(date(2020, 1, 1), date(2020, 1, 2), [row])
    with pytest.raises(CalculatorValidationError, match="daily_states"):
        CalculatorResult(row, [], (), summary)
    with pytest.raises(CalculatorValidationError, match="events"):
        CalculatorResult(row, (), [], summary)
    with pytest.raises(CalculatorValidationError, match="config"):
        CalculatorResult(object(), (), (), summary)
    with pytest.raises(CalculatorValidationError, match="summary"):
        CalculatorResult(row, (), (), object())
    request = CalculatorRequest(date(2020, 1, 1), date(2020, 1, 2), (row,))
    result = CalculatorResult(row, (), (), summary)
    assert not hasattr(request, "__dict__")
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        request.rows = ()
    with pytest.raises(FrozenInstanceError):
        row.name = "已修改"
    with pytest.raises(FrozenInstanceError):
        result.events = ()


@pytest.mark.parametrize(
    ("enum_type", "bad_value"),
    [
        (Cadence, "fortnightly"),
        (StopFamily, "threshold"),
        (CalculatorEventType, "dividend"),
        (PercentageKind, "fee"),
    ],
)
def test_enums_reject_unknown_values(enum_type: type, bad_value: str) -> None:
    # Given: an unsupported enum value.
    # When/Then: enum construction rejects it.
    with pytest.raises(ValueError):
        enum_type(bad_value)


@pytest.mark.parametrize(
    "amount",
    [0.0, -1.0, math.nan, math.inf, -math.inf, 0.999, 10_000_000.01, 1.001],
)
def test_row_rejects_invalid_contribution_amount(amount: float) -> None:
    # Given: an amount outside the finite ¥1–¥10,000,000/two-decimal contract.
    # When/Then: row construction rejects it.
    with pytest.raises(CalculatorValidationError, match="contribution_amount"):
        StrategyRowConfig(
            "无效金额",
            amount,
            Cadence.MONTHLY,
            StopFamily.NONE,
        )


@pytest.mark.parametrize(
    ("stop_family", "target", "drawdown", "fraction", "recycle"),
    [
        (StopFamily.NONE, 0.2, None, None, False),
        (StopFamily.NONE, None, 0.1, None, False),
        (StopFamily.NONE, None, None, 1.0, False),
        (StopFamily.NONE, None, None, None, True),
        (StopFamily.TARGET_RETURN, None, None, 1.0, False),
        (StopFamily.TARGET_RETURN, 0.2, 0.1, 1.0, False),
        (StopFamily.TARGET_RETURN, 0.2, None, None, False),
        (StopFamily.TRAILING_DRAWDOWN, 0.2, None, 1.0, False),
    ],
)
def test_row_rejects_incompatible_stop_fields(
    stop_family: StopFamily,
    target: float | None,
    drawdown: float | None,
    fraction: float | None,
    recycle: bool,
) -> None:
    # Given: stop-only fields that do not match the selected stop family.
    # When/Then: row construction rejects the illegal state.
    with pytest.raises(CalculatorValidationError):
        _row(
            stop_family=stop_family,
            target_return=target,
            trailing_drawdown=drawdown,
            sale_fraction=fraction,
            recycle_proceeds=recycle,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target_return", 0.0),
        ("target_return", -0.1),
        ("target_return", 5.001),
        ("target_return", math.nan),
        ("trailing_drawdown", 0.0),
        ("trailing_drawdown", 0.991),
        ("trailing_drawdown", math.inf),
        ("sale_fraction", 0.0),
        ("sale_fraction", 1.001),
        ("sale_fraction", -math.inf),
    ],
)
def test_row_rejects_invalid_stop_percentages(field: str, value: float) -> None:
    # Given: one percentage outside its decimal domain.
    values = {
        "target_return": 0.2,
        "trailing_drawdown": 0.1,
        "sale_fraction": 1.0,
    }
    values[field] = value

    # When/Then: trailing-stop construction rejects the percentage.
    with pytest.raises(CalculatorValidationError, match=field):
        _row(
            stop_family=StopFamily.TRAILING_DRAWDOWN,
            target_return=values["target_return"],
            trailing_drawdown=values["trailing_drawdown"],
            sale_fraction=values["sale_fraction"],
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
    ],
)
def test_percentage_parser_rejects_malformed_or_out_of_range_input(
    kind: PercentageKind,
    raw: str,
) -> None:
    # Given: malformed, non-finite, imprecise, or out-of-range pasted input.
    # When/Then: parsing fails before a row can be produced.
    with pytest.raises(CalculatorValidationError):
        parse_percentage(kind, raw)


@pytest.mark.parametrize(
    ("start", "end", "rows"),
    [
        ("2019-02-30", "2020-01-01", (_row(),)),
        ("2019/01/01", "2020-01-01", (_row(),)),
        ("2020-01-02", "2020-01-01", (_row(),)),
        ("2019-01-01", "2020-01-01", ()),
        ("2019-01-01", "2020-01-01", tuple(_row(str(index)) for index in range(6))),
    ],
)
def test_request_parser_rejects_invalid_dates_or_row_count(
    start: str,
    end: str,
    rows: tuple[StrategyRowConfig, ...],
) -> None:
    # Given: invalid date text, reversed coverage, or an invalid row count.
    # When/Then: parsing fails without producing a request.
    with pytest.raises(CalculatorValidationError):
        CalculatorRequest.from_user_input(start, end, rows)
