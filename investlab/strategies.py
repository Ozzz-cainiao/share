from __future__ import annotations

from dataclasses import dataclass

from investlab.models import StrategyContext, StrategyProtocol
from investlab.utils import month_diff


@dataclass
class DcaStrategy(StrategyProtocol):
    name: str = "dca"
    display_name: str = "每月定投"

    def reset(self) -> None:
        return

    def should_buy(self, ctx: StrategyContext) -> bool:
        return ctx.is_month_start


@dataclass
class DrawdownTimingStrategy(StrategyProtocol):
    drawdown_threshold: float
    max_wait_months: int

    def __post_init__(self) -> None:
        self.name = f"dd{int(self.drawdown_threshold * 100)}_{self.max_wait_months}"
        self.display_name = (
            f"固定参数(回撤{int(self.drawdown_threshold * 100)}%/等待{self.max_wait_months}个月)"
        )

    def reset(self) -> None:
        return

    def should_buy(self, ctx: StrategyContext) -> bool:
        if ctx.oldest_waiting_date is None:
            return False

        drawdown = 1.0 - (ctx.price / ctx.peak_price) if ctx.peak_price > 0 else 0.0
        trigger = drawdown >= self.drawdown_threshold
        forced = month_diff(ctx.oldest_waiting_date, ctx.date) >= self.max_wait_months
        return trigger or forced


def parse_drawdown_rules(rule_text: str) -> list[tuple[float, int]]:
    """
    Parse rules like: '10:6,20:12'
    Return: [(0.10, 6), (0.20, 12)]
    """
    rules: list[tuple[float, int]] = []
    for token in rule_text.split(","):
        token = token.strip()
        if not token:
            continue
        left, right = token.split(":")
        rules.append((float(left) / 100.0, int(right)))
    return rules


# ---- Multi-asset rebalance strategies ----

@dataclass
class NoRebalanceStrategy:
    """Equal-weight initial buy, never rebalance. BASELINE."""
    name: str = "noreb"
    display_name: str = "不调仓（等权买入后持有）"
    _first_call: bool = True

    def reset(self) -> None:
        self._first_call = True

    def get_target_weights(self, ctx) -> dict[str, float]:
        if self._first_call:
            self._first_call = False
            n = len(ctx.prices)
            return {k: 1.0 / n for k in ctx.prices} if n > 0 else {}
        return ctx.current_weights


@dataclass
class EqualWeightCalendarStrategy:
    """Periodic equal-weight rebalancing.

    frequency: "monthly", "quarterly", or "annual".
    Quarterly = months 1,4,7,10. Annual = month 1.
    """
    frequency: str = "monthly"

    def __post_init__(self) -> None:
        valid = {"monthly", "quarterly", "annual"}
        if self.frequency not in valid:
            raise ValueError(f"frequency must be one of {valid}, got {self.frequency!r}")
        self.name = f"ew_{self.frequency}"
        freq_label = {"monthly": "月度", "quarterly": "季度", "annual": "年度"}[self.frequency]
        self.display_name = f"等权再平衡({freq_label})"

    def reset(self) -> None:
        return

    def get_target_weights(self, ctx) -> dict[str, float]:
        month = ctx.date.month
        do_rebalance = False
        if self.frequency == "monthly":
            do_rebalance = True
        elif self.frequency == "quarterly":
            do_rebalance = month in {1, 4, 7, 10}
        elif self.frequency == "annual":
            do_rebalance = month == 1

        if do_rebalance:
            n = len(ctx.prices)
            return {k: 1.0 / n for k in ctx.prices} if n > 0 else {}
        return ctx.current_weights


@dataclass
class ThresholdRebalanceStrategy:
    """Rebalance to equal-weight when any asset's weight deviates > threshold."""
    threshold: float = 0.05

    def __post_init__(self) -> None:
        if self.threshold <= 0:
            raise ValueError(f"threshold must be > 0, got {self.threshold}")
        pct = int(self.threshold * 100)
        self.name = f"thresh_{pct}"
        self.display_name = f"阈值再平衡({pct}%偏离)"

    def reset(self) -> None:
        return

    def get_target_weights(self, ctx) -> dict[str, float]:
        n = len(ctx.prices)
        if n == 0:
            return {}
        equal_w = 1.0 / n
        max_dev = max(abs(ctx.current_weights.get(k, 0.0) - equal_w) for k in ctx.prices)
        if max_dev > self.threshold:
            return {k: equal_w for k in ctx.prices}
        return ctx.current_weights
