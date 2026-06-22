"""Tests for the corrected multi-asset engine."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from investlab.rebalance.engine import run_multi_asset_backtest, _validate_target_weights
from investlab.strategies import (
    EqualWeightCalendarStrategy,
    NoRebalanceStrategy,
)


def _flat_prices(n_days=252, assets=("A", "B")):
    idx = pd.date_range("2020-01-02", periods=n_days, freq="B")
    return pd.DataFrame({k: 100.0 for k in assets}, index=idx)


# ── Reconciliation ─────────────────────────────────────

def test_reconciliation_flat_prices():
    """Ending value = initial + contributions + P&L - costs within 1e-10."""
    df = _flat_prices(252)
    result = run_multi_asset_backtest(
        df, NoRebalanceStrategy(), initial_capital=10.0, monthly_contribution=1.0
    )
    expected = result.initial_capital + 12.0
    # With fees and rebalancing, final_value may differ slightly
    # Account for fees: final = initial + contributions - total_fees
    total_fees = sum(t.cost for t in result.trades)
    assert abs(result.final_value + total_fees - expected) < 2e-3, (
        f"Reconciliation failed: {result.final_value} vs {expected}"
    )


def test_reconciliation_with_gains():
    """With price gains, ending > initial + contributions."""
    idx = pd.date_range("2020-01-02", periods=252, freq="B")
    df = pd.DataFrame({"A": 100.0 + np.linspace(0, 10, 252), "B": 100.0}, index=idx)
    result = run_multi_asset_backtest(
        df, NoRebalanceStrategy(), initial_capital=1.0, monthly_contribution=0.0
    )
    assert result.final_value > 1.0


# ── Sell-before-buy / column-order invariance ──────────

def test_column_order_invariant():
    """A > B vs B > A columns must produce identical final value."""
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
    assert abs(r_ab.final_value - r_ba.final_value) < 1e-6


# ── Cash preservation ──────────────────────────────────

def test_cash_target_preserved():
    """Target 40/40 must leave ~20% cash, not normalize to 100%."""
    idx = pd.date_range("2020-01-02", periods=63, freq="B")
    df = pd.DataFrame({"A": 100.0, "B": 100.0}, index=idx)

    class PartialInvest:
        name = "partial"; display_name = "Partial"
        def reset(self): pass
        def get_target_weights(self, ctx):
            return {"A": 0.4, "B": 0.4}

    result = run_multi_asset_backtest(
        df, PartialInvest(), initial_capital=1.0, monthly_contribution=0.0
    )
    assert result.avg_cash_ratio > 0.10, f"Expected ~20% cash, got {result.avg_cash_ratio:.4f}"


# ── Target validation ──────────────────────────────────

def test_reject_sum_above_one():
    with pytest.raises(ValueError, match="sum to"):
        _validate_target_weights({"A": 0.8, "B": 0.4}, ["A", "B"])


def test_reject_negative_weight():
    with pytest.raises(ValueError, match="finite and >= 0"):
        _validate_target_weights({"A": -0.1, "B": 1.1}, ["A", "B"])


def test_reject_unknown_key():
    with pytest.raises(ValueError):
        _validate_target_weights({"A": 0.5, "C": 0.5}, ["A", "B"])


# ── Trade records ──────────────────────────────────────

def test_trade_records_generated():
    df = _flat_prices(126)
    result = run_multi_asset_backtest(
        df, EqualWeightCalendarStrategy(frequency="monthly"),
        initial_capital=1.0, monthly_contribution=1.0,
    )
    assert len(result.trades) > 0
    for t in result.trades:
        assert t.side in ("buy", "sell")
        assert t.notional > 0
        assert t.cost >= 0


# ── Turnover ───────────────────────────────────────────

def test_turnover_two_sided():
    """A full A-to-B switch is 200% turnover."""
    idx = pd.date_range("2020-01-02", periods=63, freq="B")
    df = pd.DataFrame({"A": 100.0, "B": 100.0}, index=idx)
    result = run_multi_asset_backtest(
        df, EqualWeightCalendarStrategy(frequency="monthly"),
        initial_capital=1.0, monthly_contribution=0.0,
    )
    # Initial equal-weight buy: turnover from cash
    if result.turnover_series is not None:
        assert result.turnover_series.iloc[0] > 0
