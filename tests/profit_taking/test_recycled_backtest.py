from __future__ import annotations

from datetime import date

import pandas as pd  # noqa: PANDAS_OK
import pytest

from investlab.profit_taking.recycled_backtest import (
    ExternalCashFlow,
    calculate_xirr,
    run_recycled_backtest,
)
from investlab.profit_taking.simple_backtest import SimpleBacktestConfig


def test_profit_take_pool_funds_later_monthly_contributions() -> None:
    # Given: a first cycle that reaches 20%, followed by another contribution month.
    prices = pd.Series(
        [100.0, 120.0, 120.0],
        index=pd.to_datetime(["2019-01-02", "2019-02-01", "2019-03-01"]),
    )

    # When: stop proceeds are recycled into the monthly contribution pool.
    result = run_recycled_backtest(prices, SimpleBacktestConfig())

    # Then: the pool pays 1,200 yuan and only 1,800 yuan is new external capital.
    assert result.summary.scheduled_contributions == pytest.approx(3_000.0)
    assert result.summary.recycled_contributions == pytest.approx(1_200.0)
    assert result.summary.external_invested == pytest.approx(1_800.0)
    assert result.summary.total_assets == pytest.approx(2_000.0)
    assert result.summary.total_profit == pytest.approx(200.0)
    assert result.summary.cumulative_return == pytest.approx(200.0 / 1_800.0)
    assert result.summary.profit_take_count == 1


def test_xirr_uses_actual_cash_flow_dates() -> None:
    # Given: a one-year investment that grows from 1,000 to 1,100 yuan.
    cash_flows = (
        ExternalCashFlow(date(2020, 1, 1), -1_000.0),
        ExternalCashFlow(date(2021, 1, 1), 1_100.0),
    )

    # When: the annualized money-weighted return is calculated.
    annualized_return = calculate_xirr(cash_flows)

    # Then: the result is approximately 10% for the leap-year interval.
    assert annualized_return == pytest.approx(0.0997, abs=0.0002)
