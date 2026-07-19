from __future__ import annotations

import pandas as pd  # noqa: PANDAS_OK
import pytest

from investlab.profit_taking.baseline_backtest import run_baseline_backtest
from investlab.profit_taking.simple_backtest import SimpleBacktestConfig


def test_baseline_keeps_every_contribution_in_the_market() -> None:
    # Given: three monthly prices without any profit-taking rule.
    prices = pd.Series(
        [100.0, 120.0, 90.0],
        index=pd.to_datetime(["2019-01-02", "2019-02-01", "2019-03-01"]),
    )

    # When: uninterrupted DCA is used as the benchmark.
    result = run_baseline_backtest(prices, SimpleBacktestConfig())

    # Then: all capital remains invested and no reserve or sale is created.
    assert result.summary.total_invested == pytest.approx(3_000.0)
    assert result.summary.reserve_pool == 0.0
    assert result.summary.profit_take_count == 0
    assert result.profit_takes == ()
    assert result.summary.current_holding_value == pytest.approx(2_650.0)
    assert result.summary.total_assets == pytest.approx(2_650.0)
