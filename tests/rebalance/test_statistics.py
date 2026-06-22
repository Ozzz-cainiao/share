"""Inference and bootstrap tests."""
import numpy as np
from investlab.rebalance.statistics import (
    moving_block_bootstrap,
    holm_adjust,
    regime_attribution,
    parameter_surface,
)

def test_bootstrap_confidence_interval():
    np.random.seed(42)
    excess = np.random.randn(120) * 0.02 + 0.005  # slight positive
    result = moving_block_bootstrap(excess, block_size=6, n_replicates=1000, seed=20260622)
    assert "ci_lower" in result
    assert "ci_upper" in result
    assert result["ci_lower"] <= result["mean"] <= result["ci_upper"]
    assert 0 <= result["p_value"] <= 1

def test_bootstrap_reproducibility():
    np.random.seed(42)
    excess = np.random.randn(100) * 0.02
    r1 = moving_block_bootstrap(excess, seed=20260622)
    r2 = moving_block_bootstrap(excess, seed=20260622)
    assert r1["mean"] == r2["mean"]
    assert r1["p_value"] == r2["p_value"]

def test_zero_excess_interval_covers_zero():
    np.random.seed(42)
    excess = np.random.randn(200) * 0.01  # near zero
    result = moving_block_bootstrap(excess, block_size=6, n_replicates=500, seed=20260622)
    assert result["ci_lower"] <= 0 <= result["ci_upper"]

def test_holm_monotonic():
    pvs = [("A", 0.001), ("B", 0.01), ("C", 0.05)]
    result = holm_adjust(pvs)
    for r in result:
        assert r["holm_p"] >= r["raw_p"]
    # monotonic
    for i in range(len(result) - 1):
        assert result[i]["holm_p"] <= result[i + 1]["holm_p"] + 1e-10

def test_regime_attribution_min_months():
    import pandas as pd
    idx = pd.date_range("2015-01-01", periods=60, freq="ME")
    rets = pd.DataFrame({"strat": np.random.randn(60) * 0.02}, index=idx)
    regimes = pd.Series(["bull"] * 30 + ["bear"] * 30, index=idx)
    result = regime_attribution(rets["strat"], regimes, min_months=24)
    assert len(result) == 2

def test_parameter_surface_parses_blend():
    summaries = [
        {"strategy_name": "blend_0.50_5bp", "sharpe_twr": 0.5, "ann_return_twr": 0.08, "max_drawdown_twr": -0.15, "avg_turnover": 0.3},
        {"strategy_name": "blend_0.75_10bp", "sharpe_twr": 0.6, "ann_return_twr": 0.09, "max_drawdown_twr": -0.12, "avg_turnover": 0.4},
        {"strategy_name": "noreb", "sharpe_twr": 0.3},
    ]
    df = parameter_surface(summaries)
    assert len(df) == 2
    assert df.iloc[0]["lambda"] == 0.5
