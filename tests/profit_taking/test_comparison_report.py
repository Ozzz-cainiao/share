from __future__ import annotations

import pandas as pd  # noqa: PANDAS_OK

from investlab.profit_taking.baseline_backtest import run_baseline_backtest
from investlab.profit_taking.comparison_report import render_comparison_report
from investlab.profit_taking.drawdown_backtest import run_drawdown_backtest
from investlab.profit_taking.partial_backtest import run_partial_backtest
from investlab.profit_taking.recycled_backtest import run_recycled_backtest
from investlab.profit_taking.simple_backtest import (
    SimpleBacktestConfig,
    run_simple_backtest,
)


def test_comparison_report_appends_all_profit_taking_scenarios() -> None:
    # Given: identical prices and contribution rules for both cash-handling scenarios.
    prices = pd.Series(
        [100.0, 120.0, 120.0],
        index=pd.to_datetime(["2019-01-02", "2019-02-01", "2019-03-01"]),
    )
    config = SimpleBacktestConfig()
    baseline = run_baseline_backtest(prices, config)
    retained = run_simple_backtest(prices, config)
    recycled = run_recycled_backtest(prices, config)
    partial = run_partial_backtest(prices, config)
    drawdown = run_drawdown_backtest(prices, config)

    # When: the cumulative research page is rendered.
    report = render_comparison_report(
        baseline,
        retained,
        recycled,
        partial,
        drawdown,
        provider="fixture",
        checksum="abc123",
    )

    # Then: the baseline appears first and the new scenario is appended below it.
    baseline_heading = "基准：持续定投，从不止盈"
    retained_heading = "方案一：止盈所得不再投入"
    recycled_heading = "方案二：止盈所得全部投入定投资金池"
    partial_heading = "方案三：每次止盈 50% 持仓"
    drawdown_heading = "方案四：收益达到 20% 后，"
    assert baseline_heading in report
    assert retained_heading in report
    assert recycled_heading in report
    assert partial_heading in report
    assert drawdown_heading in report
    assert 'class="nowrap">回撤 10%</span> 全部止盈' in report
    assert (
        report.index(baseline_heading)
        < report.index(retained_heading)
        < report.index(recycled_heading)
        < report.index(partial_heading)
        < report.index(drawdown_heading)
    )
    assert "一个基准，" in report
    assert "四种止盈处理方式" in report
    assert "相对基准盈利差额" in report
    assert "止盈资金池" in report
    assert "资金池循环投入" in report
    assert "XIRR 年化收益率" in report
    assert "<caption>50% 止盈记录</caption>" in report
    assert "fixture" in report
    assert "abc123" in report
