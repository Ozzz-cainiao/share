from __future__ import annotations

import math

import numpy as np
import pandas as pd

from investlab.models import BacktestResult, StrategyContext, StrategyProtocol


def run_backtest(
    prices: pd.Series,
    strategy: StrategyProtocol,
    monthly_contribution: float = 1.0,
    annual_cash_rate: float = 0.02,
    fee_rate: float = 0.0003,
) -> BacktestResult:
    if prices.empty:
        raise ValueError("prices is empty")

    strategy.reset()

    month_first_days = prices.index.to_series().groupby(prices.index.to_period("M")).min()
    month_first_set = set(month_first_days.tolist())
    rolling_peak = prices.cummax()
    daily_cash_rate = (1.0 + annual_cash_rate) ** (1.0 / 252.0) - 1.0

    cash = 0.0
    shares = 0.0
    pending_buy = False
    waiting_cash_dates: list[pd.Timestamp] = []
    trade_count = 0
    buy_dates: list[pd.Timestamp] = []
    total_contribution = 0.0

    portfolio_values: list[float] = []
    invest_ratios: list[float] = []
    cashflows: list[tuple[pd.Timestamp, float]] = []

    for i, (dt, px) in enumerate(prices.items()):
        cash *= 1.0 + daily_cash_rate

        if pending_buy and cash > 1e-12:
            invest_amount = cash * (1.0 - fee_rate)
            shares += invest_amount / px
            cash = 0.0
            waiting_cash_dates.clear()
            pending_buy = False
            trade_count += 1
            buy_dates.append(dt)

        is_month_start = dt in month_first_set
        if is_month_start:
            cash += monthly_contribution
            total_contribution += monthly_contribution
            waiting_cash_dates.append(dt)
            cashflows.append((dt, -monthly_contribution))

        ctx = StrategyContext(
            date=dt,
            price=float(px),
            peak_price=float(rolling_peak.iat[i]),
            is_month_start=is_month_start,
            oldest_waiting_date=waiting_cash_dates[0] if waiting_cash_dates else None,
        )
        should_buy = strategy.should_buy(ctx)
        if i < len(prices) - 1 and cash > 1e-12 and should_buy:
            pending_buy = True

        stock_value = shares * px
        total_value = stock_value + cash
        ratio = stock_value / total_value if total_value > 1e-12 else 0.0
        portfolio_values.append(total_value)
        invest_ratios.append(ratio)

    equity_curve = pd.Series(portfolio_values, index=prices.index, name="equity")
    drawdown_curve = equity_curve / equity_curve.cummax() - 1.0

    final_value = float(equity_curve.iat[-1])
    final_cashflows = cashflows + [(equity_curve.index[-1], final_value)]

    return BacktestResult(
        strategy_name=strategy.name,
        display_name=strategy.display_name,
        equity_curve=equity_curve,
        drawdown_curve=drawdown_curve,
        final_value=final_value,
        total_contribution=total_contribution,
        trade_count=trade_count,
        avg_invest_ratio=float(np.mean(invest_ratios)) if invest_ratios else math.nan,
        cashflows=final_cashflows,
        buy_dates=buy_dates,
    )
