"""Corrected multi-asset types with explicit accounting."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import pandas as pd


@dataclass(frozen=True)
class MultiAssetContext:
    date: pd.Timestamp
    prices: dict[str, float]
    current_weights: dict[str, float]
    current_values: dict[str, float]
    cash: float
    total_value: float
    price_history: pd.DataFrame
    is_month_start: bool


class MultiAssetStrategyProtocol(Protocol):
    name: str
    display_name: str
    family: str = ""

    def reset(self) -> None: ...
    def get_target_weights(self, ctx: MultiAssetContext) -> dict[str, float]: ...


@dataclass
class ExternalFlow:
    date: pd.Timestamp
    amount: float  # positive = deposit, negative = withdrawal
    label: str = ""


@dataclass
class TradeRecord:
    date: pd.Timestamp
    asset: str
    side: str  # "buy" | "sell"
    notional: float  # pre-fee value
    cost: float  # fee amount
    shares: float
    price: float
    post_trade_weight: float


@dataclass
class MultiAssetBacktestResult:
    strategy_name: str
    display_name: str
    equity_curve: pd.Series
    nav_curve: pd.Series  # TWR NAV starting at 1.0
    final_value: float
    total_contribution: float
    initial_capital: float
    trade_count: int
    avg_cash_ratio: float
    cashflows: list[tuple[pd.Timestamp, float]]
    rebalance_dates: list[pd.Timestamp]
    asset_equity_curves: dict[str, pd.Series]
    trades: list[TradeRecord] = field(default_factory=list)
    external_flows: list[ExternalFlow] = field(default_factory=list)
    turnover_series: pd.Series | None = None
    daily_returns: pd.Series | None = None
