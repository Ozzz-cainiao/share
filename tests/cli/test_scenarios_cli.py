from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

sys.path.insert(0, str(ROOT))


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "investlab.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_scenarios_list_exits_zero_and_shows_asset_registry_rows() -> None:
    result = run_cli("scenarios", "list")
    assert result.returncode == 0
    assert "large-cap" in result.stdout
    assert "H00300" in result.stdout


def test_top_level_help_exits_zero_and_documents_new_command_surface() -> None:
    result = run_cli("--help")
    assert result.returncode == 0
    assert "scenarios" in result.stdout
    assert "run" in result.stdout
    assert "publish" in result.stdout


def test_run_unknown_scenario_exits_nonzero_and_lists_supported_keys() -> None:
    result = run_cli("run", "not-a-scenario")
    assert result.returncode != 0
    assert "framework" in result.stderr


def test_framework_scenario_is_registered_in_the_scenario_registry() -> None:
    from investlab.scenarios import SCENARIO_REGISTRY
    from investlab.scenarios.framework_scenario import run_framework

    assert "framework" in SCENARIO_REGISTRY.keys()
    entry = SCENARIO_REGISTRY.get("framework")
    assert entry.run is run_framework
