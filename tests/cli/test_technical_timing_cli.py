from __future__ import annotations

from tests.cli.test_scenarios_cli import run_cli


def test_technical_timing_scenario_is_visible_in_cli_help() -> None:
    result = run_cli("run", "technical-timing", "--help")

    assert result.returncode == 0
    assert "--start-date" in result.stdout
    assert "--csv-dir" in result.stdout
