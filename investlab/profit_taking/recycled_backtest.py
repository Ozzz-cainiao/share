from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import pandas as pd  # noqa: PANDAS_OK

from investlab.profit_taking.simple_backtest import (
    SimpleBacktestConfig,
    SimpleBacktestError,
    SimpleProfitTake,
    _reached_target,
    _validated_prices,
)


@dataclass(frozen=True, slots=True)
class ExternalCashFlow:
    date: date
    amount: float


@dataclass(frozen=True, slots=True)
class RecycledDailyRow:
    date: date
    close: float
    contribution: float
    pool_funded: float
    external_contribution: float
    shares: float
    cycle_invested: float
    funding_pool: float
    holding_value: float
    total_assets: float


@dataclass(frozen=True, slots=True)
class RecycledSummary:
    start_date: date
    end_date: date
    trading_days: int
    contribution_count: int
    scheduled_contributions: float
    recycled_contributions: float
    external_invested: float
    funding_pool: float
    current_holding_value: float
    total_assets: float
    total_profit: float
    cumulative_return: float
    annualized_return: float
    profit_take_count: int


@dataclass(frozen=True, slots=True)
class RecycledBacktestResult:
    config: SimpleBacktestConfig
    daily_rows: tuple[RecycledDailyRow, ...]
    profit_takes: tuple[SimpleProfitTake, ...]
    external_cash_flows: tuple[ExternalCashFlow, ...]
    summary: RecycledSummary


def run_recycled_backtest(
    prices: pd.Series,
    config: SimpleBacktestConfig,
) -> RecycledBacktestResult:
    selected = _validated_prices(prices, config.start_date)
    shares = 0.0
    cycle_invested = 0.0
    funding_pool = 0.0
    external_invested = 0.0
    recycled_contributions = 0.0
    contribution_count = 0
    previous_month: tuple[int, int] | None = None
    rows: list[RecycledDailyRow] = []
    profit_takes: list[SimpleProfitTake] = []
    cash_flows: list[ExternalCashFlow] = []

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
            funding_pool += proceeds
            shares = 0.0
            cycle_invested = 0.0

        contribution = 0.0
        pool_funded = 0.0
        external_contribution = 0.0
        current_month = (current_date.year, current_date.month)
        if current_month != previous_month:
            contribution = config.monthly_contribution
            pool_funded = min(funding_pool, contribution)
            external_contribution = contribution - pool_funded
            funding_pool -= pool_funded
            recycled_contributions += pool_funded
            external_invested += external_contribution
            if external_contribution > 0:
                cash_flows.append(
                    ExternalCashFlow(current_date, -external_contribution)
                )
            shares += contribution / close
            cycle_invested += contribution
            contribution_count += 1
            previous_month = current_month

        holding_value = shares * close
        rows.append(
            RecycledDailyRow(
                date=current_date,
                close=close,
                contribution=contribution,
                pool_funded=pool_funded,
                external_contribution=external_contribution,
                shares=shares,
                cycle_invested=cycle_invested,
                funding_pool=funding_pool,
                holding_value=holding_value,
                total_assets=funding_pool + holding_value,
            )
        )

    final_row = rows[-1]
    total_profit = final_row.total_assets - external_invested
    terminal_flows = (
        *cash_flows,
        ExternalCashFlow(final_row.date, final_row.total_assets),
    )
    summary = RecycledSummary(
        start_date=rows[0].date,
        end_date=final_row.date,
        trading_days=len(rows),
        contribution_count=contribution_count,
        scheduled_contributions=contribution_count * config.monthly_contribution,
        recycled_contributions=recycled_contributions,
        external_invested=external_invested,
        funding_pool=funding_pool,
        current_holding_value=final_row.holding_value,
        total_assets=final_row.total_assets,
        total_profit=total_profit,
        cumulative_return=total_profit / external_invested,
        annualized_return=calculate_xirr(terminal_flows),
        profit_take_count=len(profit_takes),
    )
    return RecycledBacktestResult(
        config=config,
        daily_rows=tuple(rows),
        profit_takes=tuple(profit_takes),
        external_cash_flows=tuple(cash_flows),
        summary=summary,
    )


def calculate_xirr(cash_flows: tuple[ExternalCashFlow, ...]) -> float:
    if len(cash_flows) < 2 or cash_flows[-1].amount <= 0:
        raise SimpleBacktestError(
            "cash_flows",
            "must contain external investments followed by terminal assets",
        )
    origin = cash_flows[0].date

    def net_present_value(rate: float) -> float:
        return sum(
            flow.amount / math.pow(1.0 + rate, (flow.date - origin).days / 365.2425)
            for flow in cash_flows
        )

    lower = -0.999999
    upper = 1.0
    while net_present_value(upper) > 0 and upper < 1_000_000:
        upper *= 2.0
    if net_present_value(lower) < 0 or net_present_value(upper) > 0:
        raise SimpleBacktestError("cash_flows", "do not have a unique XIRR")
    for _ in range(200):
        midpoint = (lower + upper) / 2.0
        value = net_present_value(midpoint)
        if abs(value) < 1e-10:
            return midpoint
        if value > 0:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0
