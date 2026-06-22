"""Corrected multi-asset backtest engine with sell-before-buy and cash preservation."""
from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from investlab.rebalance.models import (
    ExternalFlow,
    MultiAssetBacktestResult,
    MultiAssetContext,
    MultiAssetStrategyProtocol,
    TradeRecord,
)


def _validate_target_weights(
    target: dict[str, float], asset_keys: list[str]
) -> None:
    """Reject invalid target weights with clear messages."""
    if not target:
        raise ValueError("target weights dict is empty")
    for k in asset_keys:
        if k not in target:
            raise ValueError(f"target weights missing key {k!r}")
    w_sum = sum(target.values())
    if w_sum > 1.0 + 1e-6:
        raise ValueError(
            f"target weights sum to {w_sum:.6f} > 1.0, must be <= 1.0. "
            f"Excess {(w_sum - 1.0) * 100:.2f}% must not be silently normalized."
        )
    for k, v in target.items():
        if not math.isfinite(v) or v < 0:
            raise ValueError(f"target weight for {k!r} is {v}, must be finite and >= 0")
        if k not in asset_keys:
            raise ValueError(f"target weight key {k!r} not in assets {asset_keys}")


def _project_to_simplex(
    weights: dict[str, float], bounds: dict[str, tuple[float, float]] | None = None
) -> dict[str, float]:
    """Project weights onto the simplex. Simple proportional normalization for now."""
    total = sum(weights.values())
    if total < 1e-12:
        n = len(weights)
        return {k: 1.0 / n for k in weights}
    return {k: v / total for k, v in weights.items()}


def run_multi_asset_backtest(
    prices_df: pd.DataFrame,
    strategy: MultiAssetStrategyProtocol,
    monthly_contribution: float = 0.0,
    initial_capital: float = 1.0,
    annual_cash_rate: float = 0.02,
    fee_rate: float = 0.0003,
) -> MultiAssetBacktestResult:
    """Corrected multi-asset backtest.

    Key corrections vs legacy engine:
    - Sell BEFORE buy (not buy before sell)
    - Preserve explicit cash targets (no silent normalization)
    - Track exact trade notional/cost records
    - Separate external flows from performance (TWR)
    """
    if prices_df.empty or prices_df.columns.empty:
        raise ValueError("prices_df is empty")

    # Align dates
    common_idx = prices_df.dropna().index
    if len(common_idx) == 0:
        raise ValueError("prices_df has no common non-NaN dates")
    aligned = prices_df.loc[common_idx].ffill()

    asset_keys = list(aligned.columns)
    n_assets = len(asset_keys)

    strategy.reset()

    # Month detection
    month_first_days = aligned.index.to_series().groupby(
        aligned.index.to_period("M")
    ).min()
    month_first_set = set(month_first_days.tolist())
    daily_cash_rate = (1.0 + annual_cash_rate) ** (1.0 / 252.0) - 1.0

    # State
    cash = initial_capital
    positions: dict[str, float] = {k: 0.0 for k in asset_keys}
    total_contribution = initial_capital
    trade_count = 0
    rebalance_dates: list[pd.Timestamp] = []
    trades: list[TradeRecord] = []
    external_flows: list[ExternalFlow] = []

    # TWR tracking
    nav_values: list[float] = [1.0]  # starts at 1.0
    portfolio_values: list[float] = []
    cash_ratios: list[float] = []
    cashflows: list[tuple[pd.Timestamp, float]] = []
    turnover_values: list[float] = []

    # Record initial capital as external flow
    if initial_capital > 0:
        external_flows.append(ExternalFlow(date=aligned.index[0], amount=initial_capital, label="initial_capital"))
        cashflows.append((aligned.index[0], -initial_capital))

    prev_post_flow_value: float | None = None

    for i, (dt, row) in enumerate(aligned.iterrows()):
        # Accrue daily interest on cash
        cash *= 1.0 + daily_cash_rate

        # Mark to market
        current_prices = {k: float(row[k]) for k in asset_keys}
        current_vals = {k: positions[k] * current_prices[k] for k in asset_keys}
        stock_total = sum(current_vals.values())
        pre_flow_value = stock_total + cash

        # Compute TWR return if we have a prior post-flow value
        if prev_post_flow_value is not None and prev_post_flow_value > 1e-12:
            twr_return = pre_flow_value / prev_post_flow_value - 1.0
            nav_values.append(nav_values[-1] * (1.0 + twr_return))

        # Month-start: add contribution
        is_month_start = dt in month_first_set
        if is_month_start and monthly_contribution > 0:
            cash += monthly_contribution
            total_contribution += monthly_contribution
            cashflows.append((dt, -monthly_contribution))
            external_flows.append(ExternalFlow(date=dt, amount=monthly_contribution, label="monthly"))

        # Recompute post-flow value
        post_flow_value = sum(positions[k] * current_prices[k] for k in asset_keys) + cash

        # Build context
        current_weights = (
            {k: current_vals[k] / stock_total for k in asset_keys}
            if stock_total > 1e-12
            else {k: 1.0 / n_assets for k in asset_keys}
        )

        ctx = MultiAssetContext(
            date=dt,
            prices=current_prices,
            current_weights=current_weights,
            current_values=current_vals,
            cash=cash,
            total_value=post_flow_value,
            price_history=aligned.loc[:dt],
            is_month_start=is_month_start,
        )

        # Rebalance at month-start
        if is_month_start:
            target_weights = strategy.get_target_weights(ctx)
            if target_weights:
                _validate_target_weights(target_weights, asset_keys)
                # Normalize ONLY if sum < 1 (leave cash), NOT if sum > 1 (error)
                w_sum = sum(target_weights.values())
                if w_sum < 1.0 - 1e-10:
                    # Partial investment: leave residual cash
                    pass
                elif w_sum > 1.0 + 1e-6:
                    raise ValueError(f"Target weights sum {w_sum:.6f} > 1.0")
                # w_sum ~= 1.0: full investment

                pre_trade_value = post_flow_value
                turnover_notional = 0.0

                # Phase 1: SELL first (raise cash)
                sell_orders: list[tuple[str, float]] = []
                for k in asset_keys:
                    tw = target_weights.get(k, 0.0)
                    target_val = tw * pre_trade_value
                    current_val = current_vals.get(k, 0.0)
                    if current_val > target_val + pre_trade_value * 0.0001:
                        sell_notional = current_val - target_val
                        sell_orders.append((k, sell_notional))

                for k, sell_notional in sell_orders:
                    px = current_prices[k]
                    if px <= 0 or positions[k] <= 0:
                        continue
                    shares_to_sell = sell_notional / px
                    shares_to_sell = min(shares_to_sell, positions[k])
                    proceeds = shares_to_sell * px * (1.0 - fee_rate)
                    cost = shares_to_sell * px * fee_rate
                    positions[k] -= shares_to_sell
                    cash += proceeds
                    trade_count += 1
                    turnover_notional += shares_to_sell * px
                    # Post-trade weight
                    post_trade_val = positions[k] * px
                    new_total = sum(positions[ak] * current_prices[ak] for ak in asset_keys) + cash
                    post_weight = post_trade_val / new_total if new_total > 1e-12 else 0.0
                    trades.append(TradeRecord(
                        date=dt, asset=k, side="sell",
                        notional=shares_to_sell * px, cost=cost,
                        shares=-shares_to_sell, price=px,
                        post_trade_weight=post_weight,
                    ))

                # Recompute after sells
                post_sell_value = sum(positions[k] * current_prices[k] for k in asset_keys) + cash

                # Phase 2: BUY second (using available cash)
                buy_orders: list[tuple[str, float]] = []
                for k in asset_keys:
                    tw = target_weights.get(k, 0.0)
                    target_val = tw * pre_trade_value
                    current_val = positions[k] * current_prices[k]
                    if target_val > current_val + pre_trade_value * 0.0001:
                        buy_notional = target_val - current_val
                        buy_orders.append((k, buy_notional))

                for k, buy_notional in buy_orders:
                    available = cash * (1.0 - fee_rate)
                    if available <= 0:
                        break
                    actual_buy = min(buy_notional, available / (1.0 - fee_rate))
                    invest = actual_buy * (1.0 - fee_rate)
                    cost = actual_buy * fee_rate
                    px = current_prices[k]
                    if px <= 0:
                        continue
                    positions[k] += invest / px
                    cash -= actual_buy
                    trade_count += 1
                    turnover_notional += actual_buy
                    post_trade_val = positions[k] * px
                    new_total = sum(positions[ak] * current_prices[ak] for ak in asset_keys) + cash
                    post_weight = post_trade_val / new_total if new_total > 1e-12 else 0.0
                    trades.append(TradeRecord(
                        date=dt, asset=k, side="buy",
                        notional=actual_buy, cost=cost,
                        shares=invest / px, price=px,
                        post_trade_weight=post_weight,
                    ))

                if turnover_notional > 0:
                    rebalance_dates.append(dt)
                    turnover_values.append(turnover_notional / pre_trade_value if pre_trade_value > 1e-12 else 0.0)

        # End-of-day value
        stock_total = sum(positions[k] * float(row[k]) for k in asset_keys)
        total_value = stock_total + cash
        portfolio_values.append(total_value)
        cash_ratios.append(cash / total_value if total_value > 1e-12 else 0.0)
        prev_post_flow_value = post_flow_value

    # Build results
    equity_curve = pd.Series(portfolio_values, index=aligned.index, name="equity")
    nav_curve = pd.Series(nav_values, index=aligned.index[:len(nav_values)], name="nav")
    final_value = float(equity_curve.iat[-1])
    final_cashflows = cashflows + [(equity_curve.index[-1], final_value)]

    asset_equity_curves = {
        k: pd.Series(
            [positions[k] * float(aligned.loc[dt, k]) for dt in aligned.index],
            index=aligned.index, name=k,
        )
        for k in asset_keys
    }

    turnover_s = pd.Series(turnover_values, index=rebalance_dates, name="turnover") if rebalance_dates else None

    daily_rets = nav_curve.pct_change().dropna() if len(nav_curve) > 1 else pd.Series(dtype=float)

    return MultiAssetBacktestResult(
        strategy_name=strategy.name,
        display_name=strategy.display_name,
        equity_curve=equity_curve,
        nav_curve=nav_curve,
        final_value=final_value,
        total_contribution=total_contribution,
        initial_capital=initial_capital,
        trade_count=trade_count,
        avg_cash_ratio=float(np.mean(cash_ratios)) if cash_ratios else 0.0,
        cashflows=final_cashflows,
        rebalance_dates=rebalance_dates,
        asset_equity_curves=asset_equity_curves,
        trades=trades,
        external_flows=external_flows,
        turnover_series=turnover_s,
        daily_returns=daily_rets,
    )


# Backward compatibility
from investlab.engine import run_backtest  # noqa: F401, E402
