from __future__ import annotations

import pandas as pd  # noqa: PANDAS_OK
import pytest

from investlab.profit_taking.simple_backtest import (
    SimpleBacktestConfig,
    run_simple_backtest,
)


def _prices(values: dict[str, float]) -> pd.Series:
    return pd.Series(values, dtype=float).set_axis(pd.to_datetime(list(values)))


def test_full_profit_take_when_cycle_return_reaches_exactly_twenty_percent() -> None:
    # Given: two monthly contributions whose combined holding reaches exactly 20%.
    prices = _prices(
        {
            "2019-01-02": 100.0,
            "2019-02-01": 100.0,
            "2019-02-02": 120.0,
            "2019-03-01": 120.0,
        }
    )

    # When: the simple monthly DCA strategy runs.
    result = run_simple_backtest(prices, SimpleBacktestConfig())

    # Then: the whole position is moved to reserve and monthly DCA resumes.
    assert result.summary.total_invested == pytest.approx(3_000.0)
    assert result.summary.reserve_pool == pytest.approx(2_400.0)
    assert result.summary.current_holding_value == pytest.approx(1_000.0)
    assert result.summary.total_assets == pytest.approx(3_400.0)
    assert result.summary.total_profit == pytest.approx(400.0)
    assert result.summary.profit_take_count == 1
    assert result.profit_takes[0].cycle_return == pytest.approx(0.20)
    assert result.profit_takes[0].shares_sold == pytest.approx(20.0)


def test_float_noise_does_not_miss_exact_twenty_percent_threshold() -> None:
    prices = _prices({"2019-01-02": 0.17, "2019-01-03": 0.204})

    result = run_simple_backtest(prices, SimpleBacktestConfig())

    assert result.summary.profit_take_count == 1
    assert result.summary.reserve_pool == pytest.approx(1_200.0)


def test_profit_take_precedes_same_day_monthly_contribution() -> None:
    # Given: the 20% target is first reached on the next month's first trading day.
    prices = _prices({"2019-01-02": 100.0, "2019-02-01": 120.0})

    # When: the day is processed.
    result = run_simple_backtest(prices, SimpleBacktestConfig())

    # Then: the old cycle is fully sold before a fresh 1,000 yuan cycle starts.
    assert result.summary.reserve_pool == pytest.approx(1_200.0)
    assert result.summary.current_holding_value == pytest.approx(1_000.0)
    assert result.daily_rows[-1].cycle_invested == pytest.approx(1_000.0)
    assert result.daily_rows[-1].shares == pytest.approx(1_000.0 / 120.0)


def test_summary_uses_total_assets_minus_all_external_contributions() -> None:
    # Given: a flat path without profit-taking.
    prices = _prices({"2019-01-02": 100.0, "2019-02-01": 100.0, "2019-02-28": 100.0})

    # When: the result is summarized.
    result = run_simple_backtest(prices, SimpleBacktestConfig())

    # Then: profit and return reconcile to external contributions.
    assert result.summary.total_invested == pytest.approx(2_000.0)
    assert result.summary.total_assets == pytest.approx(2_000.0)
    assert result.summary.total_profit == pytest.approx(0.0)
    assert result.summary.total_return == pytest.approx(0.0)


def test_config_rejects_nonpositive_inputs() -> None:
    with pytest.raises(ValueError, match="monthly_contribution"):
        SimpleBacktestConfig(monthly_contribution=0.0)
    with pytest.raises(ValueError, match="target_return"):
        SimpleBacktestConfig(target_return=0.0)


def test_prices_must_be_sorted_positive_and_finite() -> None:
    unsorted = pd.Series(
        [100.0, 101.0],
        index=pd.to_datetime(["2019-01-03", "2019-01-02"]),
    )
    invalid = pd.Series(
        [100.0, float("nan")], index=pd.date_range("2019-01-01", periods=2)
    )

    with pytest.raises(ValueError, match="strictly increasing"):
        run_simple_backtest(unsorted, SimpleBacktestConfig())
    with pytest.raises(ValueError, match="positive finite"):
        run_simple_backtest(invalid, SimpleBacktestConfig())


def test_prices_reject_non_numeric_closes_with_domain_error() -> None:
    prices = pd.Series(
        ["not-a-number", "100"],
        index=pd.date_range("2019-01-01", periods=2),
    )

    with pytest.raises(ValueError, match="numeric"):
        run_simple_backtest(prices, SimpleBacktestConfig())
