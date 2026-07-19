from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import pandas as pd  # noqa: PANDAS_OK


@dataclass(frozen=True, slots=True)
class SimpleBacktestError(ValueError):
    field: str
    reason: str

    def __str__(self) -> str:
        return f"{self.field}: {self.reason}"


@dataclass(frozen=True, slots=True)
class SimpleBacktestConfig:
    start_date: date = date(2019, 1, 1)
    monthly_contribution: float = 1_000.0
    target_return: float = 0.20

    def __post_init__(self) -> None:
        if (
            not math.isfinite(self.monthly_contribution)
            or self.monthly_contribution <= 0
        ):
            raise SimpleBacktestError(
                "monthly_contribution",
                "must be finite and positive",
            )
        if not math.isfinite(self.target_return) or self.target_return <= 0:
            raise SimpleBacktestError(
                "target_return",
                "must be finite and positive",
            )


@dataclass(frozen=True, slots=True)
class SimpleDailyRow:
    date: date
    close: float
    contribution: float
    shares: float
    cycle_invested: float
    reserve_pool: float
    holding_value: float
    total_assets: float


@dataclass(frozen=True, slots=True)
class SimpleProfitTake:
    sequence: int
    date: date
    close: float
    shares_sold: float
    cycle_invested: float
    proceeds: float
    cycle_profit: float
    cycle_return: float


@dataclass(frozen=True, slots=True)
class SimpleSummary:
    start_date: date
    end_date: date
    trading_days: int
    contribution_count: int
    total_invested: float
    reserve_pool: float
    current_holding_value: float
    total_assets: float
    total_profit: float
    total_return: float
    profit_take_count: int


@dataclass(frozen=True, slots=True)
class SimpleBacktestResult:
    config: SimpleBacktestConfig
    daily_rows: tuple[SimpleDailyRow, ...]
    profit_takes: tuple[SimpleProfitTake, ...]
    summary: SimpleSummary


def run_simple_backtest(
    prices: pd.Series,
    config: SimpleBacktestConfig,
) -> SimpleBacktestResult:
    selected = _validated_prices(prices, config.start_date)
    shares = 0.0
    cycle_invested = 0.0
    reserve_pool = 0.0
    total_invested = 0.0
    contribution_count = 0
    previous_month: tuple[int, int] | None = None
    rows: list[SimpleDailyRow] = []
    profit_takes: list[SimpleProfitTake] = []

    for timestamp, raw_close in selected.items():
        current_date = timestamp.date()
        close = float(raw_close)
        holding_before_flow = shares * close
        if shares > 0 and _reached_target(
            holding_before_flow,
            cycle_invested,
            config.target_return,
        ):
            proceeds = holding_before_flow
            profit_takes.append(
                SimpleProfitTake(
                    sequence=len(profit_takes) + 1,
                    date=current_date,
                    close=close,
                    shares_sold=shares,
                    cycle_invested=cycle_invested,
                    proceeds=proceeds,
                    cycle_profit=proceeds - cycle_invested,
                    cycle_return=proceeds / cycle_invested - 1.0,
                )
            )
            reserve_pool += proceeds
            shares = 0.0
            cycle_invested = 0.0

        contribution = 0.0
        current_month = (current_date.year, current_date.month)
        if current_month != previous_month:
            contribution = config.monthly_contribution
            shares += contribution / close
            cycle_invested += contribution
            total_invested += contribution
            contribution_count += 1
            previous_month = current_month

        holding_value = shares * close
        rows.append(
            SimpleDailyRow(
                date=current_date,
                close=close,
                contribution=contribution,
                shares=shares,
                cycle_invested=cycle_invested,
                reserve_pool=reserve_pool,
                holding_value=holding_value,
                total_assets=reserve_pool + holding_value,
            )
        )

    final_row = rows[-1]
    total_profit = final_row.total_assets - total_invested
    summary = SimpleSummary(
        start_date=rows[0].date,
        end_date=final_row.date,
        trading_days=len(rows),
        contribution_count=contribution_count,
        total_invested=total_invested,
        reserve_pool=reserve_pool,
        current_holding_value=final_row.holding_value,
        total_assets=final_row.total_assets,
        total_profit=total_profit,
        total_return=total_profit / total_invested,
        profit_take_count=len(profit_takes),
    )
    return SimpleBacktestResult(
        config=config,
        daily_rows=tuple(rows),
        profit_takes=tuple(profit_takes),
        summary=summary,
    )


def _validated_prices(prices: pd.Series, start_date: date) -> pd.Series:
    if prices.empty:
        raise SimpleBacktestError("prices", "must not be empty")
    if not isinstance(prices.index, pd.DatetimeIndex):
        raise SimpleBacktestError("prices", "index must contain trading dates")
    if not prices.index.is_monotonic_increasing or not prices.index.is_unique:
        raise SimpleBacktestError("prices", "dates must be strictly increasing")
    try:
        values = prices.astype(float)
    except (TypeError, ValueError) as error:
        raise SimpleBacktestError("prices", "closes must be numeric") from error
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise SimpleBacktestError("prices", "closes must be positive finite values")
    selected = values.loc[values.index.date >= start_date]
    if selected.empty:
        raise SimpleBacktestError("prices", "no observations on or after start_date")
    return selected


def _reached_target(
    holding_value: float,
    cycle_invested: float,
    target_return: float,
) -> bool:
    if cycle_invested <= 0:
        return False
    cycle_return = holding_value / cycle_invested - 1.0
    return cycle_return >= target_return or math.isclose(
        cycle_return,
        target_return,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )
