from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_framework_scenario_is_registered_in_the_scenario_registry() -> None:
    from investlab.scenarios import SCENARIO_REGISTRY

    assert "framework" in SCENARIO_REGISTRY.keys()


def test_framework_scenario_run_produces_summary_with_synthetic_prices(
    monkeypatch, tmp_path
) -> None:
    from investlab.scenarios import framework_scenario

    dates = pd.date_range("2018-01-01", "2020-12-31", freq="D")
    prices = pd.Series(
        range(100, 100 + len(dates)), index=dates, name="H00300", dtype=float
    )
    monkeypatch.setattr(
        framework_scenario, "fetch_price_series", lambda spec, start, end: prices
    )

    args = argparse.Namespace(
        start="2018-01-01",
        end="2020-12-31",
        assets="H00300",
        drawdown_rules="10:6",
        monthly=1.0,
        cash_rate=0.02,
        fee_rate=0.0003,
        output_dir=tmp_path / "framework",
    )
    rc = framework_scenario.run(args)
    assert rc == 0
    assert (tmp_path / "framework" / "summary_long.csv").exists()
