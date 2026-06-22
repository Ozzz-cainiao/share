from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_page_wraps_title_and_body_into_html_document() -> None:
    from investlab.publish.site_builder import page

    rendered = page("测试标题", "<p>body</p>")
    assert "<title>测试标题</title>" in rendered
    assert "<p>body</p>" in rendered
    assert rendered.startswith("<!doctype html>")


def test_build_site_writes_index_and_asset_pages_with_synthetic_closes(
    monkeypatch, tmp_path
) -> None:
    from investlab.publish import site_builder

    dates = pd.date_range("2017-01-01", "2020-12-31", freq="D")
    closes = pd.Series(
        range(100, 100 + len(dates)), index=dates, name="H00300", dtype=float
    )
    monkeypatch.setattr(
        site_builder, "fetch_asset_closes", lambda asset, sy, ey: closes
    )

    args = argparse.Namespace(
        assets="large-cap",
        start_year=2018,
        end_year=2020,
        input_root=tmp_path,
        site_dir=tmp_path / "site",
    )
    rc = site_builder.build_site(args)
    assert rc == 0
    site = tmp_path / "site"
    assert (site / "index.html").exists()
    assert (site / "methodology.html").exists()
    assert (site / "assets" / "site.css").exists()
    assert (site / ".nojekyll").exists()
    assert (site / "assets" / "large-cap" / "index.html").exists()
    assert (site / "assets" / "large-cap" / "lump-sum.html").exists()
    assert (site / "assets" / "large-cap" / "dca.html").exists()
    assert (site / "assets" / "large-cap" / "difference.html").exists()
    assert (site / "assets" / "large-cap" / "lump-sum.csv").exists()
