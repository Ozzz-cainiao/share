"""Clean strategic and rebalancing benchmarks with metadata."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class StrategyMeta:
    strategy_id: str
    chinese_name: str
    family: str  # "drift", "calendar", "threshold", "inverse_vol", "momentum", "blend", "regime"
    formula: str
    evaluation_frequency: str  # "monthly" | "continuous"
    parameters: dict[str, Any] = field(default_factory=dict)
    risks: list[str] = field(default_factory=list)


def _equal_target(ctx) -> dict[str, float]:
    n = len(ctx.prices)
    return {k: 1.0 / n for k in ctx.prices} if n > 0 else {}


def _inverse_vol_target(ctx, lookback: int = 63) -> dict[str, float]:
    """Trailing inverse-volatility targets bounded 10%-65%."""
    n = len(ctx.prices)
    if n == 0:
        return {}
    vols = {}
    for k in ctx.prices:
        if k in ctx.price_history.columns:
            rets = ctx.price_history[k].pct_change().dropna().tail(lookback)
            vols[k] = float(rets.std()) if len(rets) > 5 and rets.std() > 1e-12 else 1.0
        else:
            vols[k] = 1.0
    if all(v < 1e-12 for v in vols.values()):
        return _equal_target(ctx)
    inv_vols = {k: 1.0 / vols[k] for k in vols}
    total = sum(inv_vols.values())
    raw = {k: v / total for k, v in inv_vols.items()}
    # Bound to 10%-65%
    bounded = {}
    for k in raw:
        bounded[k] = max(0.10, min(0.65, raw[k]))
    b_sum = sum(bounded.values())
    return {k: v / b_sum for k, v in bounded.items()} if b_sum > 0 else _equal_target(ctx)


# ── Strategies ────────────────────────────────────────

@dataclass
class DriftStrategy:
    """Initial allocation only, never rebalance or sell."""
    name: str = "drift"
    display_name: str = "自然漂移（仅初始配置）"
    family: str = "drift"
    _first: bool = True
    meta: StrategyMeta = field(default_factory=lambda: StrategyMeta(
        "drift", "自然漂移", "drift", "初始等权后永不调仓",
        "monthly", {}, ["权重可能极度集中于赢家"]
    ))

    def reset(self): self._first = True
    def get_target_weights(self, ctx):
        if self._first:
            self._first = False
            return _equal_target(ctx)
        return ctx.current_weights


@dataclass
class ContributionOnlyStrategy:
    """New money toward target, never sell existing."""
    name: str = "contrib_only"
    display_name: str = "仅增量再平衡（不卖出）"
    family: str = "drift"
    meta: StrategyMeta = field(default_factory=lambda: StrategyMeta(
        "contrib_only", "仅增量再平衡", "drift",
        "新增资金按等权分配，不卖出存量", "monthly", {}
    ))

    def reset(self): pass
    def get_target_weights(self, ctx):
        return _equal_target(ctx)  # new money targets equal weight


@dataclass
class CalendarEqualWeight:
    frequency: str = "monthly"
    name: str = ""
    display_name: str = ""
    family: str = "calendar"
    meta: StrategyMeta | None = None

    def __post_init__(self):
        freq_label = {"monthly": "月度", "quarterly": "季度", "annual": "年度"}[self.frequency]
        self.name = f"ew_{self.frequency}"
        self.display_name = f"等权再平衡({freq_label})"
        self.meta = StrategyMeta(
            self.name, self.display_name, "calendar",
            f"每{freq_label}恢复等权", self.frequency,
            {"frequency": self.frequency},
            ["趋势市中过早减仓赢家"]
        )

    def reset(self): pass
    def get_target_weights(self, ctx):
        month = ctx.date.month
        do = (self.frequency == "monthly" or
              (self.frequency == "quarterly" and month in {1, 4, 7, 10}) or
              (self.frequency == "annual" and month == 1))
        return _equal_target(ctx) if do else ctx.current_weights


@dataclass
class ThresholdEqualWeight:
    threshold: float = 0.05
    name: str = ""
    display_name: str = ""
    family: str = "threshold"
    meta: StrategyMeta | None = None

    def __post_init__(self):
        pct = int(self.threshold * 100)
        self.name = f"thresh_{pct}"
        self.display_name = f"阈值再平衡({pct}%偏离)"
        self.meta = StrategyMeta(
            self.name, self.display_name, "threshold",
            f"任偏离超{pct}%即恢复等权", "monthly",
            {"threshold": self.threshold},
            ["连续大跌时可能频繁调仓"]
        )

    def reset(self): pass
    def get_target_weights(self, ctx):
        n = len(ctx.prices)
        if n == 0:
            return {}
        eq = 1.0 / n
        if max(abs(ctx.current_weights.get(k, 0.0) - eq) for k in ctx.prices) > self.threshold:
            return {k: eq for k in ctx.prices}
        return ctx.current_weights


@dataclass
class InverseVolatility:
    lookback: int = 63
    name: str = "inv_vol"
    display_name: str = "逆波动率加权"
    family: str = "inverse_vol"
    meta: StrategyMeta = field(default_factory=lambda: StrategyMeta(
        "inv_vol", "逆波动率加权", "inverse_vol",
        "63日逆波动率，10%-65%约束", "monthly",
        {"lookback": 63},
        ["波动率聚集期权重可能剧烈变化"]
    ))

    def reset(self): pass
    def get_target_weights(self, ctx):
        if len(ctx.price_history) < 63:
            return _equal_target(ctx)
        return _inverse_vol_target(ctx, self.lookback)


# Backwards compatibility re-exports
from investlab.strategies import (  # noqa: E402, F401
    EqualWeightCalendarStrategy,
    MomentumFilterRebalanceStrategy,
    MomentumWeightStrategy,
    NoRebalanceStrategy,
    ThresholdRebalanceStrategy,
)
