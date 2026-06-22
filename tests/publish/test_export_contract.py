from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_export_page_names_match_site_builder_report_filenames() -> None:
    from investlab.publish.export_contract import EXPORT_PAGE_NAMES
    from investlab.publish.report_registry import REPORT_REGISTRY

    report_filenames = {r.filename.removesuffix(".html") for r in REPORT_REGISTRY.entries()}
    assert set(EXPORT_PAGE_NAMES) == report_filenames


def test_expected_export_filename_format() -> None:
    from investlab.publish.export_contract import expected_export_filename

    assert expected_export_filename("large-cap", "lump-sum") == "large-cap-lump-sum.jpg"
    assert expected_export_filename("sp500", "dca", "png") == "sp500-dca.png"
    assert expected_export_filename("nasdaq100", "difference") == "nasdaq100-difference.jpg"


def test_expected_export_filename_rejects_unknown_page() -> None:
    from investlab.publish.export_contract import expected_export_filename

    with pytest.raises(ValueError):
        expected_export_filename("large-cap", "bogus")


def test_validate_site_for_export_detects_missing_pages(tmp_path: Path) -> None:
    from investlab.publish.export_contract import validate_site_for_export

    with pytest.raises(FileNotFoundError):
        validate_site_for_export(tmp_path, ["large-cap"])


def test_validate_site_for_export_accepts_built_site(tmp_path: Path) -> None:
    from investlab.publish.export_contract import EXPORT_PAGE_NAMES, validate_site_for_export

    asset_dir = tmp_path / "assets" / "large-cap"
    asset_dir.mkdir(parents=True)
    for page in EXPORT_PAGE_NAMES:
        (asset_dir / f"{page}.html").write_text("<html></html>")

    htmls = validate_site_for_export(tmp_path, ["large-cap"])
    assert len(htmls) == 3
    assert all(p.exists() for p in htmls)


def test_expected_export_paths_lists_three_jpgs_per_asset(tmp_path: Path) -> None:
    from investlab.publish.export_contract import expected_export_paths

    asset_dir = tmp_path / "assets" / "large-cap"
    asset_dir.mkdir(parents=True)
    for page in ("lump-sum", "dca", "difference"):
        (asset_dir / f"{page}.html").write_text("<html></html>")

    out = tmp_path / "downloads" / "wechat"
    paths = expected_export_paths(tmp_path, ["large-cap"], out)
    names = sorted(p.name for p in paths)
    assert names == ["large-cap-dca.jpg", "large-cap-difference.jpg", "large-cap-lump-sum.jpg"]
    assert all(p.parent == out for p in paths)
