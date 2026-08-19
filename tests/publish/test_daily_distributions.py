from __future__ import annotations

from datetime import date

from investlab.publish.daily_distributions import (
    IndexReturns,
    IndexSpec,
    build_distribution_site,
    build_payload,
    render_page,
)


def sample_dataset(name: str = "测试指数", code: str = "000001") -> IndexReturns:
    spec = IndexSpec("test", name, code, date(2024, 1, 2))
    dates = tuple(date(2024, 1, day) for day in range(2, 7))
    returns = (-1.2, -0.4, 0.0, 0.8, 1.7)
    return IndexReturns(spec, dates, returns)


def test_build_payload_bins_every_observation_once() -> None:
    payload = build_payload([sample_dataset()])
    series = payload["series"][0]
    assert sum(item["count"] for item in series["bins"]) == 5
    assert round(sum(item["share"] for item in series["bins"]), 3) == 100.0
    assert payload["domain"] == [-2, 2]


def test_render_page_contains_chart_contract() -> None:
    rendered = render_page(build_payload([sample_dataset()]))
    assert "每日涨跌幅分布" in rendered
    assert "测试指数" in rendered
    assert 'id="chart-grid"' in rendered
    assert "交易日占比" in rendered


def test_build_distribution_site_writes_subpage_and_home_link(tmp_path) -> None:
    site_dir = tmp_path / "site"
    site_dir.mkdir()
    (site_dir / "index.html").write_text(
        '<html><nav class="topnav"><a href="methodology.html">方法</a></nav></html>',
        encoding="utf-8",
    )

    output = build_distribution_site(
        site_dir,
        date(2024, 1, 6),
        fetcher=lambda _: [sample_dataset()],
    )

    assert output.exists()
    assert "测试指数" in output.read_text(encoding="utf-8")
    assert "daily-distributions/index.html" in (site_dir / "index.html").read_text(
        encoding="utf-8"
    )
