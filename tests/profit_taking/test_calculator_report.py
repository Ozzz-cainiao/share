from __future__ import annotations

import json
from pathlib import Path

import pytest

from investlab.profit_taking.calculator_report import (
    CalculatorBuildError,
    build_calculator_site,
)


def _write_prices(path: Path, *, end: str = "2026-07-17") -> None:
    path.write_text(
        f"\ufeffdate,close\n2006-01-01,1121.73\n{end},6770.28\n",
        encoding="utf-8",
    )


def test_build_calculator_site_when_fixture_is_current_is_reproducible(
    tmp_path: Path,
) -> None:
    # Given: a current offline H00300 cache and two output locations.
    prices = tmp_path / "daily.csv"
    _write_prices(prices)
    first = tmp_path / "first"
    second = tmp_path / "second"

    # When: the report is built twice.
    result = build_calculator_site(first, prices_csv=prices)
    build_calculator_site(second, prices_csv=prices)

    # Then: the complete output is byte-identical and auditable.
    expected = {
        "index.html",
        "calculator.css",
        "calculator-core.js",
        "calculator-app.js",
        "calculator-chart.js",
        "assets/h00300-prices.json",
    }
    assert result.index_path == first / "index.html"
    assert {
        path.relative_to(first).as_posix()
        for path in first.rglob("*")
        if path.is_file()
    } == expected
    assert {
        path.relative_to(first).as_posix(): path.read_bytes()
        for path in first.rglob("*")
        if path.is_file()
    } == {
        path.relative_to(second).as_posix(): path.read_bytes()
        for path in second.rglob("*")
        if path.is_file()
    }
    payload = json.loads((first / "assets/h00300-prices.json").read_text())
    assert payload["provenance"]["actual_coverage"] == [
        "2006-01-01",
        "2026-07-17",
    ]
    html = result.index_path.read_text(encoding="utf-8")
    assert "不考虑手续费、税费和滑点" in html
    assert 'href="./calculator.css?v=' in html
    assert 'src="./calculator-app.js?v=' in html


@pytest.mark.parametrize("kind", ["missing", "stale", "directory", "symlink"])
def test_build_calculator_site_when_input_is_invalid_preserves_existing_site(
    tmp_path: Path,
    kind: str,
) -> None:
    # Given: an existing site and an invalid cache boundary.
    output = tmp_path / "site"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("stable", encoding="utf-8")
    prices = tmp_path / "daily.csv"
    if kind == "stale":
        _write_prices(prices, end="2026-07-16")
    elif kind == "directory":
        prices.mkdir()
    elif kind == "symlink":
        target = tmp_path / "target.csv"
        _write_prices(target)
        prices.symlink_to(target)

    # When/Then: the boundary fails before replacing the valid deliverable.
    with pytest.raises(CalculatorBuildError):
        build_calculator_site(output, prices_csv=prices)
    assert sentinel.read_text(encoding="utf-8") == "stable"
    assert list(output.iterdir()) == [sentinel]
