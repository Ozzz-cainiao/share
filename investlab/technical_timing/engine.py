from __future__ import annotations

import numpy as np
import pandas as pd  # noqa: PANDAS_OK

from investlab.technical_timing.models import IndicatorSignal


TRADING_DAYS = 252.0


def summarize_indicator_backtests(
    close: pd.Series, signals: dict[str, IndicatorSignal], fee_rate: float
) -> pd.DataFrame:
    rows: list[dict[str, float | str]] = []
    for name, signal in signals.items():
        position = _positions(signal.buy, signal.sell)
        strategy_returns = close.pct_change().fillna(0.0) * position.shift(1).fillna(
            0.0
        )
        strategy_returns = strategy_returns - position.diff().abs().fillna(
            position
        ).mul(fee_rate)
        net_value = (1.0 + strategy_returns).cumprod()
        benchmark = (1.0 + close.pct_change().fillna(0.0)).cumprod()
        strategy_cagr = _cagr(net_value)
        benchmark_cagr = _cagr(benchmark)
        trades = _trade_returns(close, position)
        rows.append(
            {
                "indicator": name,
                "category": signal.category,
                "sharpe": _sharpe(strategy_returns),
                "annual_return": strategy_cagr,
                "annual_excess": strategy_cagr - benchmark_cagr,
                "annual_volatility": strategy_returns.std(ddof=0)
                * np.sqrt(TRADING_DAYS),
                "holding_win_rate": _win_rate(trades),
                "payoff_ratio": _payoff_ratio(trades),
                "max_drawdown": _max_drawdown(net_value),
                "annual_turnover": position.diff().abs().sum()
                / max(len(position) / TRADING_DAYS, 1.0),
            }
        )
    return (
        pd.DataFrame(rows).sort_values(["category", "indicator"]).reset_index(drop=True)
    )


def signal_events_frame(signals: dict[str, IndicatorSignal]) -> pd.DataFrame:
    columns: dict[str, pd.Series] = {}
    for name, signal in signals.items():
        columns[f"{name}_buy"] = signal.buy.astype(int)
        columns[f"{name}_sell"] = signal.sell.astype(int)
    return pd.DataFrame(columns)


def equity_curves_frame(
    close: pd.Series, signals: dict[str, IndicatorSignal], fee_rate: float
) -> pd.DataFrame:
    curves: dict[str, pd.Series] = {
        "benchmark": (1.0 + close.pct_change().fillna(0.0)).cumprod()
    }
    for name, signal in signals.items():
        position = _positions(signal.buy, signal.sell)
        returns = close.pct_change().fillna(0.0) * position.shift(1).fillna(0.0)
        returns = returns - position.diff().abs().fillna(position).mul(fee_rate)
        curves[name] = (1.0 + returns).cumprod()
    return pd.DataFrame(curves)


def _positions(buy: pd.Series, sell: pd.Series) -> pd.Series:
    position = pd.Series(0.0, index=buy.index)
    held = 0.0
    for idx in buy.index:
        if bool(buy.loc[idx]):
            held = 1.0
        if bool(sell.loc[idx]):
            held = 0.0
        position.loc[idx] = held
    return position


def _cagr(net_value: pd.Series) -> float:
    clean = net_value.dropna()
    if len(clean) < 2 or clean.iloc[0] <= 0:
        return 0.0
    years = max((clean.index[-1] - clean.index[0]).days / 365.25, 1.0 / TRADING_DAYS)
    return float((clean.iloc[-1] / clean.iloc[0]) ** (1.0 / years) - 1.0)


def _sharpe(returns: pd.Series) -> float:
    vol = returns.std(ddof=0)
    if vol == 0 or np.isnan(vol):
        return 0.0
    return float(returns.mean() / vol * np.sqrt(TRADING_DAYS))


def _max_drawdown(net_value: pd.Series) -> float:
    peak = net_value.cummax()
    drawdown = net_value / peak - 1.0
    return float(abs(drawdown.min()))


def _trade_returns(close: pd.Series, position: pd.Series) -> list[float]:
    trades: list[float] = []
    entry: float | None = None
    for idx in position.index:
        current = float(position.loc[idx])
        previous = float(position.shift(1).fillna(0.0).loc[idx])
        if current == 1.0 and previous == 0.0:
            entry = float(close.loc[idx])
        if current == 0.0 and previous == 1.0 and entry is not None:
            trades.append(float(close.loc[idx]) / entry - 1.0)
            entry = None
    return trades


def _win_rate(trades: list[float]) -> float:
    if not trades:
        return 0.0
    return sum(1 for value in trades if value > 0) / len(trades)


def _payoff_ratio(trades: list[float]) -> float:
    wins = [value for value in trades if value > 0]
    losses = [abs(value) for value in trades if value < 0]
    if not wins or not losses:
        return 0.0
    return float(np.mean(wins) / np.mean(losses))
