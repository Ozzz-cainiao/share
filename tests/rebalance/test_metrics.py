"""TWR vs XIRR separation tests."""
from __future__ import annotations

import numpy as np
import pandas as pd

from investlab.rebalance.engine import run_multi_asset_backtest
from investlab.rebalance.metrics import compute_twr_metrics
from investlab.strategies import NoRebalanceStrategy


def _flat_prices(n_days=252, assets=("A", "B")):
    idx = pd.date_range("2020-01-02", periods=n_days, freq="B")
    return pd.DataFrame({k: 100.0 for k in assets}, index=idx)


def test_deposits_not_performance():
    """Flat prices + deposits must produce zero TWR. XIRR may be nonzero."""
    df = _flat_prices(252, ("A", "B"))
    result = run_multi_asset_backtest(
        df, NoRebalanceStrategy(), initial_capital=1.0, monthly_contribution=1.0
    )
    m = compute_twr_metrics(result)
    # TWR return should be near zero on flat prices (only fees and tiny cash interest)
    assert abs(m["total_return_twr"]) < 0.01, (
        f"Flat prices should have near-zero TWR, got {m['total_return_twr']:.6f}"
    )
    # Daily TWR volatility should be near zero
    assert m["ann_vol_twr"] < 0.01, (
        f"Flat prices should have near-zero vol, got {m['ann_vol_twr']:.6f}"
    )
    # TWR max drawdown should be near zero
    assert abs(m["max_drawdown_twr"]) < 0.01, (
        f"Flat prices should have near-zero DD, got {m['max_drawdown_twr']:.6f}"
    )


def test_twr_isolated_from_deposits():
    """Same price path, different contribution schedules → same TWR."""
    idx = pd.date_range("2020-01-02", periods=252, freq="B")
    df = pd.DataFrame({
        "A": 100.0 + np.linspace(0, 10, 252),
        "B": 100.0 + np.linspace(0, 5, 252),
    }, index=idx)

    r_lump = run_multi_asset_backtest(
        df, NoRebalanceStrategy(), initial_capital=1.0, monthly_contribution=0.0
    )
    r_dca = run_multi_asset_backtest(
        df, NoRebalanceStrategy(), initial_capital=1.0, monthly_contribution=1.0
    )

    m_lump = compute_twr_metrics(r_lump)
    m_dca = compute_twr_metrics(r_dca)

    # TWR should be identical (same price path, same strategy)
    assert abs(m_lump["ann_return_twr"] - m_dca["ann_return_twr"]) < 0.001, (
        f"TWR differs: lump={m_lump['ann_return_twr']:.6f} vs dca={m_dca['ann_return_twr']:.6f}"
    )
    # But XIRR should differ (different cash flow timing)
    assert abs(m_lump["xirr_investor"] - m_dca["xirr_investor"]) > 0.0001, (
        "XIRR should differ with different contribution schedules"
    )


def test_nav_starts_at_one():
    df = _flat_prices(126)
    result = run_multi_asset_backtest(
        df, NoRebalanceStrategy(), initial_capital=1.0, monthly_contribution=0.0
    )
    assert abs(result.nav_curve.iloc[0] - 1.0) < 1e-10


def test_twr_gain():
    """10% price gain with no contributions → 10% TWR."""
    idx = pd.date_range("2020-01-02", periods=252, freq="B")
    df = pd.DataFrame({"A": 100.0 + np.linspace(0, 10, 252), "B": 100.0}, index=idx)
    result = run_multi_asset_backtest(
        df, NoRebalanceStrategy(), initial_capital=1.0, monthly_contribution=0.0
    )
    m = compute_twr_metrics(result)
    assert m["total_return_twr"] > 0.03  # ~5% on A (half of port)
