"""Strategic benchmark tests."""
import numpy as np
import pandas as pd
from investlab.models import MultiAssetContext as OldCtx
from investlab.rebalance.strategies import (
    DriftStrategy,
    ContributionOnlyStrategy,
    CalendarEqualWeight,
    ThresholdEqualWeight,
    InverseVolatility,
)

def _ctx(prices=None, weights=None, n_days=126):
    idx = pd.date_range("2020-01-02", periods=n_days, freq="B")
    if prices is None:
        prices = {"A": 100.0, "B": 100.0}
    if weights is None:
        weights = {k: 1.0/len(prices) for k in prices}
    vals = {k: weights.get(k, 0) * 10000 for k in prices}
    df = pd.DataFrame({k: prices[k] for k in prices}, index=idx)
    return OldCtx(date=idx[-1], prices=prices, current_weights=weights,
                  current_values=vals, cash=0, total_value=10000,
                  price_history=df, is_month_start=True)

def test_drift_never_sells():
    s = DriftStrategy()
    ctx = _ctx()
    w1 = s.get_target_weights(ctx)
    assert abs(sum(w1.values()) - 1.0) < 0.01
    w2 = s.get_target_weights(ctx)
    assert w2 == ctx.current_weights  # never rebalance after first

def test_contribution_never_sells():
    s = ContributionOnlyStrategy()
    ctx = _ctx()
    w = s.get_target_weights(ctx)
    assert abs(sum(w.values()) - 1.0) < 0.01

def test_calendar_schedule():
    s = CalendarEqualWeight(frequency="quarterly")
    idx = pd.date_range("2020-01-02", periods=20, freq="B")
    df = pd.DataFrame({"A": 100.0, "B": 100.0}, index=idx)
    ctx_jan = OldCtx(date=pd.Timestamp("2020-01-15"), prices={"A":100,"B":100},
                     current_weights={"A":0.7,"B":0.3}, current_values={"A":7000,"B":3000},
                     cash=0, total_value=10000, price_history=df, is_month_start=True)
    assert s.get_target_weights(ctx_jan) == {"A": 0.5, "B": 0.5}

def test_threshold_boundary():
    s = ThresholdEqualWeight(threshold=0.05)
    ctx = _ctx(weights={"A": 0.49, "B": 0.51})
    assert s.get_target_weights(ctx) == {"A": 0.49, "B": 0.51}  # within band

def test_inverse_vol_bounds():
    idx = pd.date_range("2020-01-02", periods=126, freq="B")
    np.random.seed(42)
    df = pd.DataFrame({"A": 100.0 + np.arange(126)*0.1 + np.random.randn(126)*0.5, "B": 100.0 + np.random.randn(126)*0.5, "C": 100.0 + np.random.randn(126)*0.5}, index=idx)
    s = InverseVolatility()
    ctx = OldCtx(date=idx[-1], prices={"A": df["A"].iloc[-1], "B": 100.0, "C": 100.0},
                 current_weights={"A": 0.33, "B": 0.33, "C": 0.34},
                 current_values={"A": 3300, "B": 3300, "C": 3400},
                 cash=0, total_value=10000, price_history=df, is_month_start=True)
    w = s.get_target_weights(ctx)
    for v in w.values():
        assert 0.10 <= v <= 0.65, f"weight {v} out of bounds"
    assert abs(sum(w.values()) - 1.0) < 0.01
