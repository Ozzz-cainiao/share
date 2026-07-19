from __future__ import annotations

import pandas as pd  # noqa: PANDAS_OK

from investlab.profit_taking.recycled_backtest import run_recycled_backtest
from investlab.profit_taking.recycled_report import render_recycled_report
from investlab.profit_taking.simple_backtest import SimpleBacktestConfig


def test_recycled_report_explains_external_and_recycled_capital() -> None:
    # Given: a result where stop proceeds fund a later monthly contribution.
    prices = pd.Series(
        [100.0, 120.0, 120.0],
        index=pd.to_datetime(["2019-01-02", "2019-02-01", "2019-03-01"]),
    )
    result = run_recycled_backtest(prices, SimpleBacktestConfig())

    # When: the standalone recycled-capital report is rendered.
    report = render_recycled_report(result, provider="fixture", checksum="abc123")

    # Then: external input, recycled input, cumulative return, and XIRR are explicit.
    assert "外部新增投入" in report
    assert "资金池循环投入" in report
    assert "累计收益率" in report
    assert "XIRR 年化收益率" in report
    assert 'class="nowrap">止盈所得优先支付后续定投</span>' in report
    assert "fixture" in report
    assert "https://" not in report
