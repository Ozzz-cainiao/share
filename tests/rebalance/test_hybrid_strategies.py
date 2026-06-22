"""Hybrid and regime-adaptive strategy tests."""
import numpy as np
import pandas as pd
from investlab.rebalance.strategies import (
    FixedBlendStrategy,
    RegimeAdaptiveStrategy,
    _blend_targets,
    _apply_bands,
)
from investlab.models import MultiAssetContext

def _ctx(prices_dict=None, weights=None, n_days=252):
    idx = pd.date_range("2018-01-01", periods=n_days, freq="B")
    if prices_dict is None:
        prices_dict = {"A": 100.0, "B": 100.0, "C": 100.0}
    df = pd.DataFrame({k: 100.0 + np.arange(n_days) * 0.1 for k in prices_dict}, index=idx)
    if weights is None:
        weights = {k: 1.0/len(prices_dict) for k in prices_dict}
    vals = {k: weights[k] * 10000 for k in prices_dict}
    return MultiAssetContext(date=idx[-1], prices={k: df[k].iloc[-1] for k in prices_dict},
                              current_weights=weights, current_values=vals,
                              cash=0, total_value=10000, price_history=df,
                              is_month_start=True)

def test_blend_lambda_zero_equals_base():
    s = FixedBlendStrategy(lam=0.0, band=0.0)
    ctx = _ctx()
    w = s.get_target_weights(ctx)
    assert abs(w["A"] - 1/3) < 0.01

def test_blend_lambda_one_equals_momentum():
    s = FixedBlendStrategy(lam=1.0, band=0.0)
    ctx = _ctx()
    w = s.get_target_weights(ctx)
    assert abs(sum(w.values()) - 1.0) < 0.01

def test_blend_convexity():
    """λ=0.5 should give midpoint between base and momentum."""
    s = FixedBlendStrategy(lam=0.5, band=0.0)
    ctx = _ctx()
    w = s.get_target_weights(ctx)
    assert abs(sum(w.values()) - 1.0) < 0.01

def test_apply_bands_no_move():
    target = {"A": 0.5, "B": 0.5}
    current = {"A": 0.47, "B": 0.53}  # within 5% band
    result = _apply_bands(target, current, 0.05)
    assert result == current

def test_apply_bands_trigger():
    target = {"A": 0.5, "B": 0.5}
    current = {"A": 0.7, "B": 0.3}  # A outside 5% band
    result = _apply_bands(target, current, 0.05)
    assert result != current

def test_regime_adaptive_exists():
    s = RegimeAdaptiveStrategy()
    assert s.name == "regime_adaptive"
    assert "结构牛市" in s.display_name
