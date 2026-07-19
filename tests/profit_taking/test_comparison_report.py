from __future__ import annotations

import pandas as pd  # noqa: PANDAS_OK

from investlab.profit_taking.comparison_report import render_comparison_report
from investlab.profit_taking.recycled_backtest import run_recycled_backtest
from investlab.profit_taking.simple_backtest import (
    SimpleBacktestConfig,
    run_simple_backtest,
)


def test_comparison_report_appends_both_profit_taking_scenarios() -> None:
    # Given: identical prices and contribution rules for both cash-handling scenarios.
    prices = pd.Series(
        [100.0, 120.0, 120.0],
        index=pd.to_datetime(["2019-01-02", "2019-02-01", "2019-03-01"]),
    )
    config = SimpleBacktestConfig()
    retained = run_simple_backtest(prices, config)
    recycled = run_recycled_backtest(prices, config)

    # When: the cumulative research page is rendered.
    report = render_comparison_report(
        retained,
        recycled,
        provider="fixture",
        checksum="abc123",
    )

    # Then: the baseline appears first and the new scenario is appended below it.
    retained_heading = "方案一：止盈所得不再投入"
    recycled_heading = "方案二：止盈所得全部投入定投资金池"
    assert retained_heading in report
    assert recycled_heading in report
    assert report.index(retained_heading) < report.index(recycled_heading)
    assert "两种止盈资金处理方式" in report
    assert "止盈资金池" in report
    assert "资金池循环投入" in report
    assert "XIRR 年化收益率" in report
    assert "fixture" in report
    assert "abc123" in report
