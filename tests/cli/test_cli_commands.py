from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "investlab.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_scenarios_list_prints_registry_backed_rows() -> None:
    # Given: the CLI scenarios listing surface.
    result = run_cli("scenarios", "list")

    # When: the command is invoked through the module entrypoint.
    output = result.stdout

    # Then: it succeeds and shows canonical registry-backed scenario rows.
    assert result.returncode == 0
    assert "large-cap" in output
    assert "H00300" in output
    assert "nasdaq100" in output
    assert "NASDAQXNDX" in output


def test_unknown_asset_errors_are_canonical_across_cli_entry_shapes() -> None:
    # Given: both the legacy top-level flags surface and the new run/framework surface.
    legacy_result = run_cli("--assets", "DOES_NOT_EXIST", "--output-dir", "tmp/task1-invalid")
    command_result = run_cli(
        "run",
        "framework",
        "--assets",
        "DOES_NOT_EXIST",
        "--output-dir",
        "tmp/task1-invalid",
    )

    # When: an unknown compute asset key is provided.
    legacy_error = legacy_result.stderr
    command_error = command_result.stderr

    # Then: both surfaces fail through the same canonical validation path.
    assert legacy_result.returncode != 0
    assert command_result.returncode != 0
    assert legacy_error == command_error
    assert "Unknown asset key(s): DOES_NOT_EXIST" in command_error
    assert "Available asset keys:" in command_error
