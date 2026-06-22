"""Characterization tests for the base rebalance implementation.
These lock current public behavior before refactoring.
Regression tests marked as xfail will pass after T2/T3 fixes.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from investlab.engine import run_multi_asset_backtest
from investlab.scenarios.rebalance_scenario import build_rebalance_strategies
from investlab.strategies import (
    EqualWeightCalendarStrategy,
    MomentumFilterRebalanceStrategy,
    MomentumWeightStrategy,
    NoRebalanceStrategy,
    ThresholdRebalanceStrategy,
)


# ── Helpers ──────────────────────────────────────────────

def _flat_prices(n_days: int = 252, assets: tuple[str, ...] = ("A", "B")) -> pd.DataFrame:
    idx = pd.date_range("2020-01-02", periods=n_days, freq="B")
    return pd.DataFrame({k: 100.0 for k in assets}, index=idx)


def _two_asset_diverge() -> pd.DataFrame:
    """A rises 10%, B falls 10% over 126 days."""
    idx = pd.date_range("2020-01-02", periods=126, freq="B")
    a = 100.0 + np.linspace(0, 10, 126)
    b = 100.0 - np.linspace(0, 10, 126)
    return pd.DataFrame({"A": a, "B": b}, index=idx)


# ── Characterization: public strategy names ──────────────

def test_public_strategy_names_exist():
    """All five public strategies must be importable with expected names."""
    s = NoRebalanceStrategy()
    assert s.name == "noreb"
    assert "不调仓" in s.display_name

    s2 = EqualWeightCalendarStrategy(frequency="monthly")
    assert s2.name == "ew_monthly"

    s3 = ThresholdRebalanceStrategy(threshold=0.05)
    assert s3.name == "thresh_5"

    s4 = MomentumFilterRebalanceStrategy(frequency="monthly", momentum_lookback=6)
    assert s4.name == "mf_monthly_6m"

    s5 = MomentumWeightStrategy(momentum_lookback=6, top_n=2)
    assert s5.name == "mw_6m_top2"


def test_cli_strategy_factory():
    """build_rebalance_strategies must produce at least NoRebalanceStrategy."""
    class Args:
        rebalance_freqs = "monthly"
        momentum_lookbacks = "6"
        momentum_modes = "filter"
        thresholds = "0.05"
        momentum_top_n = "2"
    strats = build_rebalance_strategies(Args())
    names = [s.name for s in strats]
    assert "noreb" in names


# ── Characterization: engine semantics ───────────────────

def test_no_rebalance_semantics():
    """NoRebalanceStrategy buys equal on first call, never sells after."""
    df = _two_asset_diverge()
    result = run_multi_asset_backtest(df, NoRebalanceStrategy(), monthly_contribution=1.0)
    assert result.trade_count >= 0  # first buy counts
    assert result.final_value > 0


def test_calendar_rebalance_triggers():
    """Monthly calendar must rebalance every month."""
    df = _flat_prices(252)
    result = run_multi_asset_backtest(
        df, EqualWeightCalendarStrategy(frequency="monthly"), monthly_contribution=1.0
    )
    # With flat prices and monthly contributions, should have multiple rebalances
    assert len(result.rebalance_dates) >= 11  # ~12 months worth


def test_next_session_execution():
    """Rebalance signals at t close execute at next common close."""
    df = _two_asset_diverge()
    result = run_multi_asset_backtest(
        df, EqualWeightCalendarStrategy(frequency="monthly"), monthly_contribution=1.0
    )
    for rd in result.rebalance_dates:
        # rebalance date must be in the index
        assert rd in df.index


# ── Characterization: report filenames ───────────────────

def test_report_output_files():
    """Scenario must produce expected CSV files."""
    from investlab.scenarios.rebalance_scenario import add_arguments
    import argparse
    p = argparse.ArgumentParser()
    add_arguments(p)
    help_text = p.format_help()
    assert "--output-dir" in help_text
    assert "--assets" in help_text
    assert "--rebalance-freqs" in help_text


# ── Regression: known defects (expected failures) ───────

@pytest.mark.xfail(reason="TWR: deposits leak into equity-curve Sharpe", strict=True)
def test_regression_deposits_not_performance():
    """Deposits must NOT create spurious time-weighted returns.
    On a flat price path, any nonzero TWR means deposits leaked into performance.
    """
    df = _flat_prices(252, ("A", "B"))
    result = run_multi_asset_backtest(
        df, NoRebalanceStrategy(), monthly_contribution=1.0
    )
    daily = result.equity_curve.pct_change().dropna()
    # After deposits are excluded, TWR should be zero on flat prices
    assert daily.std() < 1e-10, f"Flat prices should have zero TWR, got std={daily.std():.6f}"


@pytest.mark.xfail(reason="Buy-before-sell: alphabetically earlier asset starves later sell", strict=True)
def test_regression_column_order_invariant():
    """Buy execution must not depend on asset column order.
    When winner A must be sold to buy loser B, having B's column
    before A must not cause insufficient-cash errors or different outcomes.
    """
    idx = pd.date_range("2020-01-02", periods=126, freq="B")
    a_rising = 100.0 + np.linspace(0, 20, 126)
    b_falling = 100.0 - np.linspace(0, 20, 126)

    df_ab = pd.DataFrame({"A": a_rising, "B": b_falling}, index=idx)
    df_ba = pd.DataFrame({"B": b_falling, "A": a_rising}, index=idx)

    r_ab = run_multi_asset_backtest(
        df_ab, EqualWeightCalendarStrategy(frequency="monthly"),
        monthly_contribution=1.0
    )
    r_ba = run_multi_asset_backtest(
        df_ba, EqualWeightCalendarStrategy(frequency="monthly"),
        monthly_contribution=1.0
    )
    assert abs(r_ab.final_value - r_ba.final_value) < 1e-6, (
        f"Column order invariant violated: {r_ab.final_value} vs {r_ba.final_value}"
    )


@pytest.mark.xfail(reason="Cash-preserve: target sum <1 must leave cash, not normalize", strict=True)
def test_regression_cash_target_preserved():
    """Target weights summing below 1.0 must leave residual cash,
    NOT be silently normalized to 100% invested.
    """
    idx = pd.date_range("2020-01-02", periods=63, freq="B")
    df = pd.DataFrame({"A": 100.0, "B": 100.0}, index=idx)

    class PartialInvest:
        name = "partial"
        display_name = "Partial"
        def reset(self): pass
        def get_target_weights(self, ctx):
            return {"A": 0.4, "B": 0.4}  # 20% cash

    result = run_multi_asset_backtest(df, PartialInvest(), monthly_contribution=1.0)
    # After initial buy, cash ratio should be ~20% (not 0%)
    assert result.avg_cash_ratio > 0.10, (
        f"Expected ~20% cash, got avg_cash_ratio={result.avg_cash_ratio:.4f}"
    )
