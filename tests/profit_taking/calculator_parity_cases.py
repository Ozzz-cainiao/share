from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final

from investlab.profit_taking.calculator_models import (
    Cadence,
    StopFamily,
    StrategyRowConfig,
)

_BASE_POINTS: Final = (
    ("2023-12-29", 100.0),
    ("2024-01-02", 119.999999),
    ("2024-01-08", 120.0),
    ("2024-01-15", 130.0),
    ("2024-02-01", 117.0),
    ("2024-02-15", 100.0),
    ("2024-03-01", 120.0),
    ("2024-03-15", 108.0),
    ("2024-04-01", 130.0),
)


@dataclass(frozen=True, slots=True)
class ParityCaseSpec:
    identifier: str
    config: StrategyRowConfig
    points: tuple[tuple[str, float], ...]
    coverage: tuple[str, ...]
    requested_start: date
    requested_end: date


def parity_case_specs() -> tuple[ParityCaseSpec, ...]:
    specs: list[ParityCaseSpec] = []
    fractions = (0.01, 0.5, 1.0)
    stop_index = 0
    for cadence in Cadence:
        for stop in StopFamily:
            if stop is StopFamily.NONE:
                config = StrategyRowConfig(
                    f"{cadence.value}-none",
                    100.0,
                    cadence,
                    stop,
                )
            else:
                config = StrategyRowConfig(
                    f"{cadence.value}-{stop.value}",
                    100.0,
                    cadence,
                    stop,
                    0.2,
                    0.1 if stop is StopFamily.TRAILING_DRAWDOWN else None,
                    fractions[stop_index % len(fractions)],
                    stop_index % 2 == 1,
                )
                stop_index += 1
            specs.append(
                ParityCaseSpec(
                    f"matrix_{cadence.value}_{stop.value}",
                    config,
                    _BASE_POINTS,
                    ("matrix",),
                    date(2023, 12, 28),
                    date(2024, 4, 2),
                )
            )
    specs.extend(_edge_specs())
    return tuple(specs)


def _edge_specs() -> tuple[ParityCaseSpec, ...]:
    return (
        _edge_target("near_threshold", 119.999999, ("near_threshold", "no_trigger")),
        _edge_target("exact_threshold", 120.0, ("exact_threshold",)),
        ParityCaseSpec(
            "edge_same_day_recycled",
            StrategyRowConfig(
                "same-day",
                100.0,
                Cadence.MONTHLY,
                StopFamily.TARGET_RETURN,
                0.2,
                None,
                1.0,
                True,
            ),
            (("2024-01-02", 100.0), ("2024-02-01", 120.0)),
            ("same_day", "recycle"),
            date(2024, 1, 2),
            date(2024, 2, 1),
        ),
        ParityCaseSpec(
            "edge_repeated_trailing_cycles",
            StrategyRowConfig(
                "repeated-cycles",
                100.0,
                Cadence.MONTHLY,
                StopFamily.TRAILING_DRAWDOWN,
                0.2,
                0.1,
                0.5,
                False,
            ),
            (
                ("2024-01-02", 100.0),
                ("2024-01-03", 120.0),
                ("2024-01-04", 108.0),
                ("2024-01-05", 129.6),
                ("2024-01-06", 116.64),
            ),
            ("exact_threshold", "repeated_cycles"),
            date(2024, 1, 2),
            date(2024, 1, 6),
        ),
    )


def _edge_target(
    identifier: str,
    terminal_price: float,
    coverage: tuple[str, ...],
) -> ParityCaseSpec:
    return ParityCaseSpec(
        f"edge_{identifier}",
        StrategyRowConfig(
            identifier.replace("_", "-"),
            100.0,
            Cadence.MONTHLY,
            StopFamily.TARGET_RETURN,
            0.2,
            None,
            1.0,
            False,
        ),
        (("2024-01-02", 100.0), ("2024-01-03", terminal_price)),
        coverage,
        date(2024, 1, 2),
        date(2024, 1, 3),
    )
