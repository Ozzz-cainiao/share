from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum, unique
from typing import Final, assert_never


@dataclass(frozen=True, slots=True)
class CalculatorValidationError(ValueError):
    field: str
    reason: str

    def __str__(self) -> str:
        return f"{self.field}: {self.reason}"


@unique
class Cadence(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


@unique
class StopFamily(StrEnum):
    NONE = "none"
    TARGET_RETURN = "target_return"
    TRAILING_DRAWDOWN = "trailing_drawdown"


@unique
class PercentageKind(StrEnum):
    TARGET_RETURN = "target_return"
    TRAILING_DRAWDOWN = "trailing_drawdown"
    SALE_FRACTION = "sale_fraction"


@unique
class CalculatorEventType(StrEnum):
    CONTRIBUTION = "contribution"
    STOP_ACTIVATION = "stop_activation"
    SALE = "sale"


_PERCENT_LIMITS: Final[dict[PercentageKind, tuple[Decimal, Decimal]]] = {
    PercentageKind.TARGET_RETURN: (Decimal("0.1"), Decimal("500")),
    PercentageKind.TRAILING_DRAWDOWN: (Decimal("0.1"), Decimal("99")),
    PercentageKind.SALE_FRACTION: (Decimal("0.1"), Decimal("100")),
}


def parse_percentage(kind: PercentageKind, value: str) -> float:
    if type(kind) is not PercentageKind:
        raise CalculatorValidationError("percentage_kind", "must be a PercentageKind")
    if type(value) is not str:
        raise CalculatorValidationError(kind.value, "must be percentage text")
    try:
        percentage = Decimal(value)
    except InvalidOperation as error:
        raise CalculatorValidationError(
            kind.value, "must be a decimal percentage"
        ) from error
    minimum, maximum = _PERCENT_LIMITS[kind]
    if not percentage.is_finite() or not minimum <= percentage <= maximum:
        raise CalculatorValidationError(
            kind.value,
            f"must be finite and inside [{minimum}, {maximum}] percent",
        )
    if percentage % Decimal("0.1") != 0:
        raise CalculatorValidationError(
            kind.value,
            "must use 0.1 percentage-point increments",
        )
    return float(percentage / Decimal(100))


def _normalize_percentage(
    kind: PercentageKind,
    value: float | None,
) -> float | None:
    if value is None:
        return None
    if type(value) not in (int, float):
        raise CalculatorValidationError(kind.value, "must be an int or float")
    return parse_percentage(kind, str(Decimal(str(value)) * Decimal(100)))


@dataclass(frozen=True, slots=True)
class StrategyRowConfig:
    name: str
    contribution_amount: float
    cadence: Cadence
    stop_family: StopFamily
    target_return: float | None = None
    trailing_drawdown: float | None = None
    sale_fraction: float | None = None
    recycle_proceeds: bool = False

    def __post_init__(self) -> None:
        if type(self.name) is not str:
            raise CalculatorValidationError("name", "must be a string")
        name = self.name.strip()
        if not name:
            raise CalculatorValidationError("name", "must be non-empty")
        object.__setattr__(self, "name", name)
        if type(self.cadence) is not Cadence:
            raise CalculatorValidationError("cadence", "must be a Cadence")
        if type(self.stop_family) is not StopFamily:
            raise CalculatorValidationError("stop_family", "must be a StopFamily")
        if type(self.contribution_amount) not in (int, float):
            raise CalculatorValidationError(
                "contribution_amount", "must be an int or float"
            )
        amount = float(self.contribution_amount)
        if (
            not math.isfinite(amount)
            or not 1 <= amount <= 10_000_000
            or Decimal(str(amount)).as_tuple().exponent < -2
        ):
            raise CalculatorValidationError(
                "contribution_amount",
                "must be finite, inside [1, 10000000], and use at most two decimals",
            )
        object.__setattr__(self, "contribution_amount", amount)
        if type(self.recycle_proceeds) is not bool:
            raise CalculatorValidationError("recycle_proceeds", "must be boolean")
        target = _normalize_percentage(PercentageKind.TARGET_RETURN, self.target_return)
        drawdown = _normalize_percentage(
            PercentageKind.TRAILING_DRAWDOWN, self.trailing_drawdown
        )
        fraction = _normalize_percentage(
            PercentageKind.SALE_FRACTION, self.sale_fraction
        )
        object.__setattr__(self, "target_return", target)
        object.__setattr__(self, "trailing_drawdown", drawdown)
        object.__setattr__(self, "sale_fraction", fraction)
        match self.stop_family:
            case StopFamily.NONE:
                if any(value is not None for value in (target, drawdown, fraction)) or (
                    self.recycle_proceeds
                ):
                    raise CalculatorValidationError(
                        "stop_family", "no-stop rows take no stop-only fields"
                    )
            case StopFamily.TARGET_RETURN:
                if target is None or fraction is None:
                    raise CalculatorValidationError(
                        "stop_family", "target and sale fraction are required"
                    )
                if drawdown is not None:
                    raise CalculatorValidationError(
                        "trailing_drawdown", "is only valid for trailing stops"
                    )
            case StopFamily.TRAILING_DRAWDOWN:
                if target is None or drawdown is None or fraction is None:
                    raise CalculatorValidationError(
                        "stop_family",
                        "target, drawdown, and sale fraction are required",
                    )
            case unreachable:
                assert_never(unreachable)


@dataclass(frozen=True, slots=True)
class CalculatorRequest:
    start_date: date
    end_date: date
    rows: tuple[StrategyRowConfig, ...]

    def __post_init__(self) -> None:
        if type(self.start_date) is not date or type(self.end_date) is not date:
            raise CalculatorValidationError("date", "must be a calendar date")
        if type(self.rows) is not tuple or any(
            type(row) is not StrategyRowConfig for row in self.rows
        ):
            raise CalculatorValidationError(
                "rows", "must be a tuple containing only StrategyRowConfig values"
            )
        if self.start_date > self.end_date:
            raise CalculatorValidationError("date_range", "start must not follow end")
        if not 1 <= len(self.rows) <= 5:
            raise CalculatorValidationError(
                "rows", "must contain between one and five rows"
            )

    @classmethod
    def from_user_input(
        cls,
        start_date: str,
        end_date: str,
        rows: tuple[StrategyRowConfig, ...],
    ) -> CalculatorRequest:
        try:
            parsed_start = date.fromisoformat(start_date)
            parsed_end = date.fromisoformat(end_date)
        except ValueError as error:
            raise CalculatorValidationError(
                "date", "must use a valid ISO YYYY-MM-DD date"
            ) from error
        return cls(parsed_start, parsed_end, rows)


@dataclass(frozen=True, slots=True)
class DailyState:
    date: date
    price: float
    scheduled_contribution: float
    external_contribution: float
    pool_contribution: float
    shares: float
    cycle_basis: float
    reusable_pool: float
    reserve: float
    holding_value: float
    total_assets: float
    nav: float


@dataclass(frozen=True, slots=True)
class CalculatorEvent:
    date: date
    event_type: CalculatorEventType
    amount: float
    shares: float
    price: float

    def __post_init__(self) -> None:
        if type(self.event_type) is not CalculatorEventType:
            raise CalculatorValidationError(
                "event_type", "must be a CalculatorEventType"
            )


@dataclass(frozen=True, slots=True)
class CalculatorSummary:
    scheduled_invested: float
    external_invested: float
    ending_holdings: float
    reusable_pool: float
    reserve: float
    total_assets: float
    total_profit: float
    cumulative_return: float
    xirr: float | None
    maximum_drawdown: float
    time_in_market: float
    stop_count: int


@dataclass(frozen=True, slots=True)
class CalculatorResult:
    config: StrategyRowConfig
    daily_states: tuple[DailyState, ...]
    events: tuple[CalculatorEvent, ...]
    summary: CalculatorSummary

    def __post_init__(self) -> None:
        if type(self.config) is not StrategyRowConfig:
            raise CalculatorValidationError("config", "must be a StrategyRowConfig")
        if type(self.summary) is not CalculatorSummary:
            raise CalculatorValidationError("summary", "must be a CalculatorSummary")
        if type(self.daily_states) is not tuple or any(
            type(state) is not DailyState for state in self.daily_states
        ):
            raise CalculatorValidationError(
                "daily_states", "must be a tuple containing only DailyState values"
            )
        if type(self.events) is not tuple or any(
            type(event) is not CalculatorEvent for event in self.events
        ):
            raise CalculatorValidationError(
                "events", "must be a tuple containing only CalculatorEvent values"
            )
