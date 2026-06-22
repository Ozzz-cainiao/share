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
    if b_sum > 0:
        normalized = {k: v / b_sum for k, v in bounded.items()}
        # Ensure float precision doesn't exceed 1.0
        s = sum(normalized.values())
        if s > 1.0001:
            normalized = {k: v / s for k, v in normalized.items()}
        return normalized
    return _equal_target(ctx)


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




# ── Fixed-ratio strategies (alternative base weights) ──

@dataclass
class FixedRatioStrategy:
    """Buy-and-hold with fixed target weights. Never rebalances after initial buy."""
    target: dict[str, float] = None
    name: str = ""
    display_name: str = ""
    family: str = "fixed_ratio"
    _first: bool = True

    def __post_init__(self):
        if self.target is None:
            self.target = {}
        if not self.name:
            parts = [f"{k}={v:.0%}" for k, v in sorted(self.target.items())]
            self.name = "fixed_" + "_".join(p.replace("%","") for p in parts).replace("=","")
        if not self.display_name:
            parts = [f"{k[-3:]}{v:.0%}" for k, v in sorted(self.target.items())]
            self.display_name = "固定比例(" + "/".join(parts) + ")"
        self.meta = StrategyMeta(
            self.name, self.display_name, "fixed_ratio",
            "初始按固定比例买入后永不调仓", "monthly",
            {"target": self.target},
            ["权重偏离目标后不纠正"]
        )

    def reset(self): self._first = True
    def get_target_weights(self, ctx):
        if self._first:
            self._first = False
            return dict(self.target)
        return ctx.current_weights


@dataclass
class FixedRatioRebalanceStrategy:
    """Monthly rebalance to fixed target weights."""
    target: dict[str, float] = None
    name: str = ""
    display_name: str = ""
    family: str = "fixed_ratio"
    meta: StrategyMeta | None = None

    def __post_init__(self):
        if self.target is None:
            self.target = {}
        if not self.name:
            self.name = "fixed_rebal_" + "_".join(
                f"{k}{int(v*100)}" for k, v in sorted(self.target.items())
            )
        if not self.display_name:
            parts = [f"{k[-3:]}{v:.0%}" for k, v in sorted(self.target.items())]
            self.display_name = "固定比例月度再平衡(" + "/".join(parts) + ")"
        self.meta = StrategyMeta(
            self.name, self.display_name, "fixed_ratio",
            "每月恢复目标比例", "monthly",
            {"target": self.target, "rebalance": True},
        )

    def reset(self): pass
    def get_target_weights(self, ctx):
        return dict(self.target)

# Backwards compatibility re-exports
from investlab.strategies import (  # noqa: E402, F401
    EqualWeightCalendarStrategy,
    MomentumFilterRebalanceStrategy,
    MomentumWeightStrategy,
    NoRebalanceStrategy,
    ThresholdRebalanceStrategy,
)


# ── Hybrid blend strategies ────────────────────────────

def _blend_targets(
    base: dict[str, float],
    momentum: dict[str, float],
    lam: float,
    assets: list[str],
) -> dict[str, float]:
    """Convex blend: (1-lam)*base + lam*momentum, projected to simplex."""
    blended = {}
    for k in assets:
        b = base.get(k, 0.0)
        m = momentum.get(k, 0.0)
        blended[k] = (1.0 - lam) * b + lam * m
    total = sum(blended.values())
    if total > 1e-12:
        # Normalize and ensure float precision
        result = {k: v / total for k, v in blended.items()}
        s = sum(result.values())
        if abs(s - 1.0) > 1e-10:
            result = {k: v / s for k, v in result.items()}
        return result
    n = len(assets)
    return {k: 1.0 / n for k in assets}


def _apply_bands(
    target: dict[str, float],
    current: dict[str, float],
    band: float,
) -> dict[str, float]:
    """Only move to target if deviation > band; otherwise stay."""
    result = {}
    has_move = False
    for k in target:
        t = target.get(k, 0.0)
        c = current.get(k, 0.0)
        if abs(t - c) > band:
            result[k] = t
            has_move = True
        else:
            result[k] = c
    if has_move:
        total = sum(result.values())
        if total > 1e-12:
            return {k: v / total for k, v in result.items()}
    return current


@dataclass
class FixedBlendStrategy:
    """Fixed convex blend of equal-weight base and momentum rank target."""
    lam: float = 0.5
    band: float = 0.05
    momentum_lookback: int = 6

    def __post_init__(self):
        bp = int(self.band * 100)
        self.name = f"blend_{self.lam:.2f}_{bp}bp"
        self.display_name = f"固定混合(λ={self.lam:.2f}/{bp}bp)"
        self.family = "blend"
        self.meta = StrategyMeta(
            self.name, self.display_name, "blend",
            f"target=(1-{self.lam})*等权+{self.lam}*动量排名, {bp}bp免调带",
            "monthly",
            {"lambda": self.lam, "band": self.band, "lookback": self.momentum_lookback},
        )

    def reset(self): pass

    def get_target_weights(self, ctx):
        from investlab.rebalance.signals import momentum_rank_target
        assets = list(ctx.prices.keys())
        base = {k: 1.0 / len(assets) for k in assets} if assets else {}
        momentum = momentum_rank_target(ctx.price_history)
        if not momentum:
            return base
        blended = _blend_targets(base, momentum, self.lam, assets)
        return _apply_bands(blended, ctx.current_weights, self.band)


@dataclass
class RegimeAdaptiveStrategy:
    """Structural-bull adaptive: higher lambda + wider sell band for leader."""
    momentum_lookback: int = 6

    def __post_init__(self):
        self.name = "regime_adaptive"
        self.display_name = "结构牛市自适应"
        self.family = "regime"
        self.meta = StrategyMeta(
            self.name, self.display_name, "regime",
            "结构牛市λ=0.75/15pp卖带，其他上升λ=0.50，其他λ=0.25",
            "monthly",
            {"lookback": self.momentum_lookback},
            ["结构牛市判定依赖历史统计，小样本不可靠"]
        )

    def reset(self): pass

    def get_target_weights(self, ctx):
        from investlab.rebalance.signals import (
            classify_regime,
            momentum_rank_target,
            momentum_score,
        )
        assets = list(ctx.prices.keys())
        n = len(assets)
        if n == 0:
            return {}

        base = {k: 1.0 / n for k in assets}
        momentum = momentum_rank_target(ctx.price_history)
        if not momentum:
            return base

        regime = classify_regime(ctx.price_history)
        scores = momentum_score(ctx.price_history)

        # Determine lambda and sell band
        if regime.is_structural_bull:
            lam = 0.75
            sell_band = 0.15
            lead_band = 0.15
        elif regime.is_uptrend:
            lam = 0.50
            sell_band = 0.05
            lead_band = 0.05
        else:
            lam = 0.25
            sell_band = 0.05
            lead_band = 0.05

        # Leading asset with positive momentum gets wider sell band
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        leader = ranked[0][0] if ranked and ranked[0][1] > 0 else None

        blended = _blend_targets(base, momentum, lam, assets)

        # Apply bands: leader gets wider sell band in structural bull
        result = {}
        for k in assets:
            t = blended.get(k, 0.0)
            c = ctx.current_weights.get(k, 0.0)
            if abs(t - c) > (lead_band if k == leader and regime.is_structural_bull else sell_band):
                result[k] = t
            else:
                result[k] = c

        # Normalize
        total = sum(result.values())
        if total > 1e-12:
            return {k: v / total for k, v in result.items()}
        return base
