from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd

from investlab.scenarios import rebalance_scenario


def _prices() -> pd.DataFrame:
    dates = pd.bdate_range("2015-01-02", periods=252 * 9)
    return pd.DataFrame(
        {
            "H00300": 100.0 * np.cumprod(np.full(len(dates), 1.00015)),
            "H00905": 100.0 * np.cumprod(np.full(len(dates), 1.00022)),
            "H00852": 100.0 * np.cumprod(np.full(len(dates), 1.00030)),
        },
        index=dates,
    )


def test_rebalance_help_documents_research_configuration() -> None:
    # Given: the rebalance scenario argument surface.
    import argparse

    parser = argparse.ArgumentParser()

    # When: arguments are registered.
    rebalance_scenario.add_arguments(parser)
    help_text = parser.format_help()

    # Then: the predeclared research knobs are visible to implementers.
    assert "--cost-grid" in help_text
    assert "--fixed-lambdas" in help_text
    assert "--fixed-bands" in help_text
    assert "--walk-forward" in help_text
    assert "--contribution-sensitivity" in help_text


def test_rebalance_run_writes_core_research_artifacts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    # Given: a deterministic synthetic index panel.
    prices = _prices()
    from investlab.rebalance.data import PanelMetadata

    meta = PanelMetadata(
        panel_type="index",
        symbols=["H00300", "H00905", "H00852"],
        names=["沪深300", "中证500", "中证1000"],
        source_endpoint="test",
        requested_start="2015-01-01",
        requested_end="2023-12-31",
        actual_start="2015-01-02",
        actual_end="2023-08-22",
        n_observations=len(prices) * 3,
        n_missing=0,
        common_dates=len(prices),
        price_sha256="synthetic",
        download_timestamp="2026-06-28T00:00:00+00:00",
    )
    monkeypatch.setattr(rebalance_scenario, "build_index_panel", lambda *_: (prices, meta))

    args = Namespace(
        start="2015-01-01",
        end="2023-12-31",
        assets="H00300,H00905,H00852",
        rebalance_freqs="monthly,quarterly,annual",
        thresholds="0.05,0.10",
        momentum_lookbacks="3,6,12",
        momentum_modes="filter,weight",
        momentum_top_n="2",
        monthly=0.0,
        cash_rate=0.02,
        fee_rate=0.0003,
        initial_capital=1.0,
        panel="index",
        output_dir=str(tmp_path),
        cost_grid="0.0005,0.0010,0.0020",
        fixed_lambdas="0,0.25,0.50,0.75,1",
        fixed_bands="0,0.05,0.10",
        walk_forward=True,
        contribution_sensitivity=False,
    )

    # When: the scenario is driven through its CLI run function.
    assert rebalance_scenario.run(args) == 0

    # Then: downstream agents get the declared machine-readable surface.
    expected = {
        "run_manifest.json",
        "strategy_catalog.json",
        "summary_full_sample.csv",
        "summary_oos.csv",
        "fold_selections.csv",
        "monthly_returns.csv",
        "regime_summary.csv",
        "parameter_surface.csv",
        "bootstrap_inference.csv",
        "turnover_costs.csv",
        "signals.csv",
        "rebalance_comparison.html",
    }
    assert expected.issubset({path.name for path in tmp_path.iterdir()})
    assert any(tmp_path.glob("nav_*.csv"))
    assert any(tmp_path.glob("weights_*.csv"))
    assert any(tmp_path.glob("trades_*.csv"))
