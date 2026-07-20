from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from investlab.profit_taking.calculator_report import (
    CalculatorBuildError,
    build_calculator_site,
)

SOURCE_PAYLOAD = Path(
    "investlab/profit_taking/calculator_source/h00300-tri-source.json"
)


def _write_prices(path: Path, *, end: str = "2026-07-17") -> None:
    source = json.loads(SOURCE_PAYLOAD.read_text(encoding="utf-8"))
    prices = [list(row) for row in source["prices"]]
    prices[-1][0] = end
    rows = "".join(f"{price_date},{close}\n" for price_date, close in prices)
    path.write_text(
        f"\ufeffdate,close\n{rows}",
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
        ".investlab-calculator-site.json",
        "index.html",
        "calculator.css",
        "calculator-core.js",
        "calculator-integrity.js",
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
        "2006-01-04",
        "2026-07-17",
    ]
    assert payload["provenance"]["requested_coverage"] == [
        "2006-01-01",
        "2026-07-17",
    ]
    assert payload["provenance"]["provider"] == "provided_csv"
    assert result.start_date.isoformat() == "2006-01-04"
    html = result.index_path.read_text(encoding="utf-8")
    assert "不考虑手续费、税费和滑点" in html
    assert 'href="./calculator.css?v=' in html
    assert 'src="./calculator-integrity.js?v=' in html
    assert 'src="./calculator-app.js?v=' in html
    assert (
        f'<meta name="calculator-data-sha256" content="{result.checksum_sha256}">'
        in html
    )
    payload_text = (first / "assets/h00300-prices.json").read_text(encoding="utf-8")
    payload_checksum = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    assert (
        f'<meta name="calculator-payload-sha256" content="{payload_checksum}">' in html
    )
    app = (first / "calculator-app.js").read_text(encoding="utf-8")
    assert "startInput.min = requestedCoverage[0]" in app
    assert "startInput.value = requestedCoverage[0]" in app


@pytest.mark.parametrize(
    "dangerous",
    [Path("/"), Path.home(), Path.cwd()],
)
def test_build_calculator_site_when_output_is_dangerous_is_rejected(
    dangerous: Path,
) -> None:
    # Given: a filesystem root, home, or workspace output target.
    # When/Then: publication rejects it before touching existing contents.
    with pytest.raises(CalculatorBuildError, match="dangerous"):
        build_calculator_site(dangerous)


@pytest.mark.parametrize("with_sentinel", [False, True])
def test_build_calculator_site_when_output_is_unmanaged_is_rejected(
    tmp_path: Path,
    with_sentinel: bool,
) -> None:
    # Given: an arbitrary existing directory that the calculator does not own.
    output = tmp_path / "documents"
    output.mkdir()
    sentinel = output / "user.txt"
    if with_sentinel:
        sentinel.write_text("keep", encoding="utf-8")

    # When/Then: publication refuses to move or delete it.
    with pytest.raises(CalculatorBuildError, match="not a managed"):
        build_calculator_site(output)
    if with_sentinel:
        assert sentinel.read_text(encoding="utf-8") == "keep"
    assert output.is_dir()


def test_build_calculator_site_when_managed_output_exists_updates_it(
    tmp_path: Path,
) -> None:
    # Given: a site created by the calculator publisher.
    output = tmp_path / "site"
    first = build_calculator_site(output)
    old_index = first.index_path.read_bytes()

    # When: the same managed destination is rebuilt.
    second = build_calculator_site(output)

    # Then: the managed marker remains and the deterministic site is replaced.
    assert second.index_path.read_bytes() == old_index
    assert (output / ".investlab-calculator-site.json").is_file()


def test_build_calculator_site_never_deletes_preexisting_backup_named_sibling(
    tmp_path: Path,
) -> None:
    # Given: a managed site and a user-owned sibling matching the old fixed name.
    output = tmp_path / "site"
    build_calculator_site(output)
    sibling = tmp_path / ".site-previous"
    sibling.mkdir()
    sentinel = sibling / "user.txt"
    sentinel.write_text("keep", encoding="utf-8")

    # When: the managed site is updated.
    build_calculator_site(output)

    # Then: the unrelated sibling is untouched.
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_default_build_uses_bundled_offline_official_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: no caller-provided CSV and an empty destination.
    output = tmp_path / "site"
    monkeypatch.setattr(
        "investlab.profit_taking.data._default_raw_loader",
        lambda *_args: pytest.fail("default build attempted a network provider"),
    )

    # When: the default calculator is built without a network dependency.
    result = build_calculator_site(output)
    payload = json.loads((output / "assets/h00300-prices.json").read_text())

    # Then: bundled official provenance and normalized coverage are reproducible.
    assert result.start_date.isoformat() == "2006-01-04"
    assert len(payload["prices"]) == 4_989
    assert payload["provenance"]["provider"].startswith("csindex_tri")
    assert payload["provenance"]["actual_coverage"] == [
        "2006-01-04",
        "2026-07-17",
    ]


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
