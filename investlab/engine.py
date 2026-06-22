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


def run_multi_asset_backtest(
    prices_df: pd.DataFrame,
    strategy: MultiAssetStrategyProtocol,
    monthly_contribution: float = 1.0,
    annual_cash_rate: float = 0.02,
    fee_rate: float = 0.0003,
) -> MultiAssetBacktestResult:
    """Run a multi-asset backtest with rebalancing.

    prices_df: DataFrame with asset keys as columns, dates as index.
    strategy: MultiAssetStrategyProtocol instance.
    """
    from investlab.models import MultiAssetContext, MultiAssetBacktestResult, MultiAssetStrategyProtocol  # noqa: F811

    if prices_df.empty or prices_df.columns.empty:
        raise ValueError("prices_df is empty")

    # Align dates: use intersection of all non-NaN dates per column
    common_idx = prices_df.dropna().index
    if len(common_idx) == 0:
        raise ValueError("prices_df has no common non-NaN dates across all assets")
    aligned = prices_df.loc[common_idx].copy()
    # Forward-fill any remaining NaN within the aligned range
    aligned = aligned.ffill()

    asset_keys = list(aligned.columns)
    n_assets = len(asset_keys)

    strategy.reset()

    month_first_days = aligned.index.to_series().groupby(
        aligned.index.to_period("M")
    ).min()
    month_first_set = set(month_first_days.tolist())
    daily_cash_rate = (1.0 + annual_cash_rate) ** (1.0 / 252.0) - 1.0

    cash = 0.0
    positions: dict[str, float] = {k: 0.0 for k in asset_keys}
    total_contribution = 0.0
    trade_count = 0
    rebalance_dates: list[pd.Timestamp] = []

    # Pending trades: list of (asset_key, target_value, is_buy)
    pending_trades: list[tuple[str, float, bool]] = []
    first_rebalance_done = False

    portfolio_values: list[float] = []
    cash_ratios: list[float] = []
    cashflows: list[tuple[pd.Timestamp, float]] = []

    # Per-asset equity tracking
    asset_values: dict[str, list[float]] = {k: [] for k in asset_keys}

    for i, (dt, row) in enumerate(aligned.iterrows()):
        # 1. Accrue daily interest
        cash *= 1.0 + daily_cash_rate

        # 2. Execute pending trades from previous day at today's prices
        net_cash_change = 0.0
        for asset_key, target_value, is_buy in pending_trades:
            px = float(row[asset_key])
            if px <= 0:
                continue
            current_value = positions[asset_key] * px
            if is_buy:
                # Buy: spend cash to acquire shares
                buy_amount = target_value - current_value
                if buy_amount > 0 and cash >= buy_amount:
                    invest = buy_amount * (1.0 - fee_rate)
                    positions[asset_key] += invest / px
                    cash -= buy_amount
                    trade_count += 1
            else:
                # Sell: sell shares to raise cash
                sell_amount = current_value - target_value
                if sell_amount > 0 and positions[asset_key] > 0:
                    shares_to_sell = sell_amount / px
                    proceeds = sell_amount * (1.0 - fee_rate)
                    positions[asset_key] -= shares_to_sell
                    cash += proceeds
                    trade_count += 1
        pending_trades.clear()

        # 3. Month-start: add contribution
        is_month_start = dt in month_first_set
        if is_month_start:
            cash += monthly_contribution
            total_contribution += monthly_contribution
            cashflows.append((dt, -monthly_contribution))

        # 4. Build context
        current_prices = {k: float(row[k]) for k in asset_keys}
        current_vals = {k: positions[k] * current_prices[k] for k in asset_keys}
        stock_total = sum(current_vals.values())
        total_value = stock_total + cash
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
            total_value=total_value,
            price_history=aligned.loc[:dt],
            is_month_start=is_month_start,
        )

        # 5. Month-start: rebalance
        if is_month_start:
            target_weights = strategy.get_target_weights(ctx)
            if target_weights:
                # Normalize to sum to 1.0
                w_sum = sum(target_weights.values())
                if w_sum > 1e-12:
                    target_weights = {k: v / w_sum for k, v in target_weights.items()}
                else:
                    target_weights = {k: 1.0 / n_assets for k in asset_keys}

                # Compute trades
                has_trades = False
                for k in asset_keys:
                    tw = target_weights.get(k, 0.0)
                    target_val = tw * total_value
                    current_val = current_vals.get(k, 0.0)
                    diff = abs(target_val - current_val)
                    if diff > total_value * 0.001:  # 0.1% tolerance
                        pending_trades.append((k, target_val, target_val > current_val))
                        has_trades = True

                if has_trades:
                    rebalance_dates.append(dt)

        # 6. Record portfolio value
        stock_total = sum(positions[k] * float(row[k]) for k in asset_keys)
        total_value = stock_total + cash
        portfolio_values.append(total_value)
        cash_ratios.append(cash / total_value if total_value > 1e-12 else 0.0)

        # Per-asset values
        for k in asset_keys:
            asset_values[k].append(positions[k] * float(row[k]))

    # Build result
    equity_curve = pd.Series(portfolio_values, index=aligned.index, name="equity")
    final_value = float(equity_curve.iat[-1])
    final_cashflows = cashflows + [(equity_curve.index[-1], final_value)]

    asset_equity_curves = {
        k: pd.Series(vals, index=aligned.index, name=k)
        for k, vals in asset_values.items()
    }

    return MultiAssetBacktestResult(
        strategy_name=strategy.name,
        display_name=strategy.display_name,
        equity_curve=equity_curve,
        final_value=final_value,
        total_contribution=total_contribution,
        trade_count=trade_count,
        avg_cash_ratio=float(np.mean(cash_ratios)) if cash_ratios else 0.0,
        cashflows=final_cashflows,
        rebalance_dates=rebalance_dates,
        asset_equity_curves=asset_equity_curves,
    )
