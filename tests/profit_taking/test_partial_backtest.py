from __future__ import annotations

import pandas as pd  # noqa: PANDAS_OK
import pytest

from investlab.profit_taking.partial_backtest import run_partial_backtest
from investlab.profit_taking.simple_backtest import SimpleBacktestConfig


def test_partial_stop_sells_half_and_rebases_remaining_holding() -> None:
    # Given: a position reaches 20% and then remains at the same price.
    prices = pd.Series(
        [100.0, 120.0, 120.0],
        index=pd.to_datetime(["2019-01-02", "2019-02-01", "2019-02-02"]),
    )

    # When: the strategy takes profit from 50% of the holding.
    result = run_partial_backtest(prices, SimpleBacktestConfig())

    # Then: only half is sold and the retained half does not immediately retrigger.
    event = result.profit_takes[0]
    assert result.summary.profit_take_count == 1
    assert event.shares_sold == pytest.approx(5.0)
    assert event.proceeds == pytest.approx(600.0)
    assert result.summary.reserve_pool == pytest.approx(600.0)
    assert result.daily_rows[-1].cycle_invested == pytest.approx(1_600.0)
    assert result.summary.total_assets == pytest.approx(2_200.0)
