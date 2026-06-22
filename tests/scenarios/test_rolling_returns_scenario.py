from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_rolling_returns_scenario_is_registered_in_the_scenario_registry() -> None:
    from investlab.scenarios import SCENARIO_REGISTRY

    assert "rolling-returns" in SCENARIO_REGISTRY.keys()


def test_rolling_returns_scenario_run_produces_matrices_with_synthetic_closes(
    monkeypatch, tmp_path
) -> None:
    from investlab.scenarios import rolling_returns_scenario
    from investlab.scenarios import rolling_returns_core

    dates = pd.date_range("2017-01-01", "2020-12-31", freq="D")
    closes = pd.Series(
        range(100, 100 + len(dates)), index=dates, name="H00300", dtype=float
    )
    monkeypatch.setattr(
        rolling_returns_core, "fetch_asset_closes", lambda asset, sy, ey: closes
    )

    args = argparse.Namespace(
        start_year=2018,
        end_year=2020,
        assets="large-cap",
        symbol=None,
        name=None,
        output_dir=tmp_path,
        no_known_adjustments=False,
    )
    rc = rolling_returns_scenario.run(args)
    assert rc == 0
    assert (tmp_path / "h00300_rolling_annualized_returns.csv").exists()
    assert (tmp_path / "h00300_rolling_annualized_returns.html").exists()
    assert (tmp_path / "index.html").exists()
