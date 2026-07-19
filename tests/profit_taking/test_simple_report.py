from __future__ import annotations

import pandas as pd  # noqa: PANDAS_OK

from investlab.profit_taking.simple_backtest import (
    SimpleBacktestConfig,
    run_simple_backtest,
)
from investlab.profit_taking.simple_report import render_simple_report


def test_report_contains_core_results_method_and_accessible_ledger() -> None:
    # Given: a result with one completed profit-taking cycle.
    prices = pd.Series(
        [100.0, 120.0],
        index=pd.to_datetime(["2019-01-02", "2019-02-01"]),
    )
    result = run_simple_backtest(prices, SimpleBacktestConfig())

    # When: the standalone report is rendered.
    report = render_simple_report(result, provider="fixture", checksum="abc123")

    # Then: the result, method, accessible chart, and ledger are all self-contained.
    assert "总投入" in report
    assert "总盈利" in report
    assert "止盈次数" in report
    assert "本轮累计收益率" in report
    assert '<title id="chart-title">沪深300定投止盈资产轨迹</title>' in report
    assert "<caption>全部止盈记录</caption>" in report
    assert "fixture" in report
    assert "abc123" in report
    assert "https://" not in report


def test_report_describes_the_result_configuration() -> None:
    prices = pd.Series(
        [100.0, 110.0],
        index=pd.to_datetime(["2019-01-02", "2019-02-01"]),
    )
    result = run_simple_backtest(
        prices,
        SimpleBacktestConfig(monthly_contribution=500.0, target_return=0.10),
    )

    report = render_simple_report(result, provider="fixture", checksum="abc123")

    assert "每月定投 500 元" in report
    assert "累计收益 10% 全部止盈" in report
    assert "投入 500 元" in report
    assert "达到或超过 10%" in report
