from __future__ import annotations

import pandas as pd  # noqa: PANDAS_OK
import pytest

from investlab.profit_taking.drawdown_backtest import run_drawdown_backtest
from investlab.profit_taking.simple_backtest import SimpleBacktestConfig


def test_drawdown_stop_arms_then_sells_all_at_ten_percent_from_peak() -> None:
    # Given: cycle ROI reaches 20%, price makes a new high, then falls exactly 10%.
    prices = pd.Series(
        [100.0, 120.0, 135.0, 121.5, 100.0],
        index=pd.to_datetime(
            [
                "2019-01-02",
                "2019-01-03",
                "2019-01-04",
                "2019-01-05",
                "2019-02-01",
            ]
        ),
    )

    # When: the activated trailing-drawdown strategy is evaluated daily.
    result = run_drawdown_backtest(prices, SimpleBacktestConfig())

    # Then: the full position is sold only after the peak-to-price drawdown reaches 10%.
    event = result.profit_takes[0]
    assert result.summary.profit_take_count == 1
    assert event.date.isoformat() == "2019-01-05"
    assert event.shares_sold == pytest.approx(10.0)
    assert event.proceeds == pytest.approx(1_215.0)
    assert result.summary.reserve_pool == pytest.approx(1_215.0)
    assert result.summary.total_invested == pytest.approx(2_000.0)
    assert result.summary.current_holding_value == pytest.approx(1_000.0)
