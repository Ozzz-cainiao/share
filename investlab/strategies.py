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
