from __future__ import annotations

import math
from datetime import date
from typing import assert_never

import pandas as pd  # noqa: PANDAS_OK

from investlab.profit_taking.calculator_models import (
    Cadence,
    CalculatorValidationError,
)


def select_price_window(
    prices: pd.Series,
    start_date: date,
    end_date: date,
) -> pd.Series:
    if prices.empty:
        raise CalculatorValidationError("prices", "must not be empty")
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise CalculatorValidationError("prices", "index must contain trading dates")
    if not prices.index.is_monotonic_increasing or not prices.index.is_unique:
        raise CalculatorValidationError("prices", "dates must be strictly increasing")
    try:
        numeric = prices.astype(float)
    except (TypeError, ValueError) as error:
        raise CalculatorValidationError("prices", "closes must be numeric") from error
    if any(not math.isfinite(value) or value <= 0 for value in numeric):
        raise CalculatorValidationError(
            "prices", "closes must be positive finite values"
        )
    selected = numeric.loc[
        (numeric.index.date >= start_date) & (numeric.index.date <= end_date)
    ]
    if selected.empty:
        raise CalculatorValidationError(
            "price_window", "contains no trading observations"
        )
    return selected


def contribution_dates(
    dates: tuple[date, ...],
    cadence: Cadence,
) -> tuple[date, ...]:
    if not dates:
        return ()
    match cadence:
        case Cadence.DAILY:
            keys = tuple(range(len(dates)))
        case Cadence.WEEKLY:
            keys = tuple(
                (value.isocalendar().year, value.isocalendar().week) for value in dates
            )
        case Cadence.BIWEEKLY:
            anchor = dates[0]
            keys = tuple((value - anchor).days // 14 for value in dates)
        case Cadence.MONTHLY:
            keys = tuple((value.year, value.month) for value in dates)
        case Cadence.QUARTERLY:
            keys = tuple((value.year, (value.month - 1) // 3) for value in dates)
        case unreachable:
            assert_never(unreachable)
    scheduled: list[date] = []
    previous: int | tuple[int, int] | None = None
    for value, key in zip(dates, keys, strict=True):
        if key != previous:
            scheduled.append(value)
            previous = key
    return tuple(scheduled)
