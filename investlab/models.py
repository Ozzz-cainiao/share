from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd


@dataclass(frozen=True)
class AssetSpec:
    key: str
    name: str
    source: str
    symbol: str
    total_return: bool = True


@dataclass(frozen=True)
class StrategyContext:
    date: pd.Timestamp
    price: float
    peak_price: float
    is_month_start: bool
    oldest_waiting_date: pd.Timestamp | None


class StrategyProtocol(Protocol):
    name: str
    display_name: str

    def reset(self) -> None:
        ...

    def should_buy(self, ctx: StrategyContext) -> bool:
        ...


@dataclass
class BacktestResult:
    strategy_name: str
    display_name: str
    equity_curve: pd.Series
    drawdown_curve: pd.Series
    final_value: float
    total_contribution: float
    trade_count: int
    avg_invest_ratio: float
    cashflows: list[tuple[pd.Timestamp, float]]
    buy_dates: list[pd.Timestamp]


@dataclass
class StrategySummary:
    asset_key: str
    asset_name: str
    strategy_name: str
    strategy_display_name: str
    final_value: float
    total_contribution: float
    xirr: float
    cagr: float
    max_drawdown: float
    ann_return: float
    ann_vol: float
    sharpe: float
    avg_invest_ratio: float
    trade_count: int
    xirr_excess: float = 0.0



@dataclass(frozen=True)
class MultiAssetContext:
    """Context passed to multi-asset strategies on each evaluation day."""
    date: pd.Timestamp
    prices: dict[str, float]
    current_weights: dict[str, float]
    current_values: dict[str, float]
    cash: float
    total_value: float
    price_history: pd.DataFrame
    is_month_start: bool


class MultiAssetStrategyProtocol(Protocol):
    """Interface for multi-asset rebalancing strategies."""
    name: str
    display_name: str

    def reset(self) -> None:
        ...

    def get_target_weights(self, ctx: MultiAssetContext) -> dict[str, float]:
        """Return target weights {asset_key: weight}. Should sum to <= 1.0."""
        ...


@dataclass
class MultiAssetBacktestResult:
    strategy_name: str
    display_name: str
    equity_curve: pd.Series
    final_value: float
    total_contribution: float
    trade_count: int
    avg_cash_ratio: float
    cashflows: list[tuple[pd.Timestamp, float]]
    rebalance_dates: list[pd.Timestamp]
    asset_equity_curves: dict[str, pd.Series]
