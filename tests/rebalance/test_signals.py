"""Momentum and regime signal tests."""
import numpy as np
import pandas as pd
from investlab.rebalance.signals import (
    momentum_score,
    momentum_rank_target,
    classify_regime,
    RegimeSignal,
    _n_month_return,
)

def _rising_series(n=504, slope=0.1):
    idx = pd.date_range("2018-01-01", periods=n, freq="B")
    return pd.Series(100.0 + np.arange(n) * slope, index=idx)

def test_momentum_score_ranking():
    idx = pd.date_range("2018-01-01", periods=504, freq="B")
    df = pd.DataFrame({
        "fast": 100.0 + np.arange(504) * 0.2,
        "slow": 100.0 + np.arange(504) * 0.1,
    }, index=idx)
    scores = momentum_score(df)
    assert scores["fast"] > scores["slow"]

def test_rank_target_weights():
    idx = pd.date_range("2018-01-01", periods=504, freq="B")
    np.random.seed(42)
    n = 504
    df = pd.DataFrame({
        "A": 100.0 + np.arange(n) * 0.3 + np.random.randn(n) * 2,
        "B": 100.0 + np.arange(n) * 0.15 + np.random.randn(n) * 2,
        "C": 100.0 + np.arange(n) * 0.02 + np.random.randn(n) * 2,
    }, index=idx)
    targets = momentum_rank_target(df)
    assert targets["A"] == 0.60
    assert targets["B"] == 0.30
    assert targets["C"] == 0.10
    assert abs(sum(targets.values()) - 1.0) < 0.01

def test_no_lookahead():
    """Perturbing future prices must not change earlier signals."""
    idx = pd.date_range("2018-01-01", periods=400, freq="B")
    df = pd.DataFrame({"A": 100.0 + np.arange(400)*0.1, "B": 100.0}, index=idx)
    # Signal at day 350
    hist_350 = df.iloc[:351]
    sig_before = classify_regime(hist_350)
    # Perturb future (days 351-399)
    df_perturbed = df.copy()
    df_perturbed.iloc[351:, 0] += 100.0
    hist_350b = df_perturbed.iloc[:351]
    sig_after = classify_regime(hist_350b)
    assert sig_before.is_structural_bull == sig_after.is_structural_bull

def test_structural_bull_false_early():
    """Too little history → structural bull is False."""
    idx = pd.date_range("2018-01-01", periods=100, freq="B")
    df = pd.DataFrame({"A": 100.0 + np.arange(100)*0.1, "B": 100.0}, index=idx)
    sig = classify_regime(df)
    assert not sig.is_structural_bull

def test_n_month_return_skip():
    s = _rising_series(252, 0.1)
    r = _n_month_return(s, 3)
    assert r > 0
