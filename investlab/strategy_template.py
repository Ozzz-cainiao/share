from __future__ import annotations

from dataclasses import dataclass

from investlab.models import StrategyContext, StrategyProtocol
from investlab.utils import month_diff


@dataclass
class TemplateStrategy(StrategyProtocol):
    """
    Copy this class when creating a new strategy.

    Rules below are only examples:
    - Buy when drawdown >= trigger_drawdown
    - Or force buy when waiting exceeds max_wait_months
    """

    trigger_drawdown: float = 0.12
    max_wait_months: int = 6

    def __post_init__(self) -> None:
        self.name = "template_12_6"
        self.display_name = "模板策略(12%/6月)"

    def reset(self) -> None:
        return

    def should_buy(self, ctx: StrategyContext) -> bool:
        if ctx.oldest_waiting_date is None:
            return False
        drawdown = 1.0 - (ctx.price / ctx.peak_price) if ctx.peak_price > 0 else 0.0
        force_buy = month_diff(ctx.oldest_waiting_date, ctx.date) >= self.max_wait_months
        return drawdown >= self.trigger_drawdown or force_buy
