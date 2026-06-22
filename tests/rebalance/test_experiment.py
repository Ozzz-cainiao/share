"""Experiment runner tests."""
import numpy as np
import pandas as pd
from investlab.rebalance.experiment import run_full_sample, run_walk_forward
from investlab.rebalance.strategies import DriftStrategy, CalendarEqualWeight

def _multi_year_prices(n_years=12):
    idx = pd.date_range("2010-01-01", periods=n_years * 252, freq="B")
    return pd.DataFrame({
        "A": 100.0 + np.arange(n_years * 252) * 0.05 + np.random.randn(n_years * 252) * 2,
        "B": 100.0 + np.arange(n_years * 252) * 0.03 + np.random.randn(n_years * 252) * 2,
        "C": 100.0 + np.arange(n_years * 252) * 0.01 + np.random.randn(n_years * 252) * 2,
    }, index=idx)

def test_full_sample_runs():
    df = _multi_year_prices(8)
    strategies = [DriftStrategy(), CalendarEqualWeight(frequency="monthly")]
    results = run_full_sample(df, strategies)
    assert len(results) == 2
    for r in results:
        assert "sharpe_twr" in r
        assert "ann_return_twr" in r

def test_walk_forward_fold_structure():
    np.random.seed(42)
    df = _multi_year_prices(10)
    candidates = [DriftStrategy(), CalendarEqualWeight(frequency="monthly"),
                  CalendarEqualWeight(frequency="quarterly")]
    baseline = DriftStrategy()
    oos, folds = run_walk_forward(df, candidates, baseline, min_train_years=5)
    # With 10 years and min 5 train + 2 val + 1 test, we should have 10-8=2 folds
    assert len(folds) >= 1

def test_walk_forward_date_order():
    np.random.seed(42)
    df = _multi_year_prices(10)
    candidates = [DriftStrategy(), CalendarEqualWeight(frequency="monthly")]
    baseline = DriftStrategy()
    oos, folds = run_walk_forward(df, candidates, baseline, min_train_years=5)
    if folds:
        for f in folds:
            assert f.train_end <= f.val_start
            assert f.val_end <= f.test_start

def test_insufficient_history():
    df = _multi_year_prices(4)  # too short
    candidates = [DriftStrategy()]
    oos, folds = run_walk_forward(df, candidates, DriftStrategy(), min_train_years=5)
    assert oos == []
    assert folds == []
