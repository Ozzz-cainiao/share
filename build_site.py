#!/usr/bin/env python3
"""Build the static GitHub Pages site under docs/.

New table families can be added to REPORTS and emitted from build_asset_site.
The public site deliberately contains generated HTML/CSV only; research code
and dependencies remain at the repository root.
"""

from __future__ import annotations

import argparse
import html
from dataclasses import dataclass
from pathlib import Path

from asset_catalog import ASSETS, AssetDefinition, asset_help, resolve_assets
from dca_comparison import build_dca_matrices, render_comparison_html
from rolling_returns import (
    apply_known_adjustments,
    build_matrix,
    fetch_csindex_closes,
    year_end_closes,
)


@dataclass(frozen=True)
class ReportDefinition:
    mode: str
    filename: str
    title: str
    description: str


# Extend this catalog when a new table family becomes publishable.
REPORTS: tuple[ReportDefinition, ...] = (
    ReportDefinition("lump", "lump-sum.html", "一次投入", "一次投入后的滚动 CAGR"),
    ReportDefinition("dca", "dca.html", "年度定投", "每年年初等额投入的滚动 IRR"),
    ReportDefinition(
        "difference", "difference.html", "定投与一次投入之差", "定投 IRR 减一次投入 CAGR"
    ),
)


SITE_CSS = """
:root{--ink:#26304a;--muted:#68758b;--line:#dce2ed;--paper:#f5f7fb;--brand:#405477;--card:#fff}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
a{color:inherit}.shell{max-width:1120px;margin:auto;padding:44px 28px 60px}.eyebrow{color:#7b879b;font-size:13px;letter-spacing:.08em;text-transform:uppercase}
h1{margin:8px 0 12px;font:600 38px Georgia,"Songti SC",serif}.lead{max-width:760px;color:var(--muted);font-size:17px;line-height:1.75}
.topnav{display:flex;gap:10px;flex-wrap:wrap;margin:22px 0 34px}.topnav a,.button{display:inline-block;padding:9px 13px;border-radius:9px;background:var(--brand);color:#fff;text-decoration:none;font-size:14px}
.section-title{margin:34px 0 14px;font-size:22px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(285px,1fr));gap:18px}.card{padding:22px;border:1px solid var(--line);border-radius:15px;background:var(--card);box-shadow:0 8px 26px rgba(35,45,75,.055)}
.card h2{margin:7px 0 5px;font-size:21px}.category,.meta{color:var(--muted);font-size:13px}.code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#8791a3}.links{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px}.links a{padding:7px 10px;border:1px solid #cdd5e3;border-radius:8px;text-decoration:none;font-size:13px}.links a:hover{background:#eef2f8}
.metric-row{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:20px 0}.metric{padding:14px;border:1px solid var(--line);border-radius:11px;background:#fff}.metric strong{display:block;margin-top:5px;font-size:22px}.notice{margin:24px 0;padding:14px 16px;border-radius:11px;background:#fff8dc;border:1px solid #dfc578;color:#665629;line-height:1.65}.prose{max-width:820px;line-height:1.8}.prose h2{margin-top:32px}.prose code{padding:2px 5px;border-radius:5px;background:#e9edf4}.footer{margin-top:46px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:13px;line-height:1.7}
@media(max-width:680px){.shell{padding:28px 16px 42px}h1{font-size:29px}.metric-row{grid-template-columns:1fr}}
"""


def page(title: str, body: str, *, depth: int = 0) -> str:
    prefix = "../" * depth
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="中国宽基指数长期收益、定投收益与一次投入对比">
<title>{html.escape(title)}</title><link rel="stylesheet" href="{prefix}assets/site.css"></head>
<body>{body}</body></html>"""


def fmt(value: float) -> str:
    return f"{value:+.2f}%"


def asset_landing(
    asset: AssetDefinition,
    start_year: int,
    end_year: int,
    lump_value: float,
    dca_value: float,
    adjustment_notes: list[str],
) -> str:
    report_links = "".join(
        f'<a href="{report.filename}">{report.title}</a>' for report in REPORTS
    )
    adjustment = ""
    if adjustment_notes:
        adjustment = f'<div class="notice">数据修正：{html.escape("；".join(adjustment_notes))}</div>'
    body = f"""<main class="shell"><div class="eyebrow">{html.escape(asset.category)} · {asset.symbol}</div>
<h1>{html.escape(asset.name)}</h1><p class="lead">{start_year}–{end_year} 年滚动收益研究。选择下方页面查看一次投入、年度定投或二者的年化收益差。</p>
<nav class="topnav"><a href="../../index.html">← 全部标的</a><a href="../../methodology.html">方法与数据</a></nav>
<div class="metric-row"><div class="metric">完整区间一次投入 CAGR<strong>{fmt(lump_value)}</strong></div><div class="metric">完整区间年度定投 IRR<strong>{fmt(dca_value)}</strong></div><div class="metric">定投 − 一次投入<strong>{fmt(dca_value-lump_value)}</strong></div></div>
{adjustment}<section><h2 class="section-title">分析表格</h2><div class="links">{report_links}</div></section>
<div class="footer">历史收益不代表未来表现。本网站仅用于数据研究与方法展示，不构成任何投资建议。</div></main>"""
    return page(f"{asset.name}｜投资收益研究", body, depth=2)


def home(selected: list[AssetDefinition], start_year: int, end_year: int) -> str:
    cards = []
    for asset in selected:
        cards.append(
            f'<article class="card"><div class="category">{html.escape(asset.category)}</div>'
            f'<h2>{html.escape(asset.name)}</h2><div class="code">{asset.symbol}</div>'
            f'<div class="links"><a href="assets/{asset.key}/index.html">进入该标的</a>'
            f'<a href="assets/{asset.key}/difference.html">直接看差值</a></div></article>'
        )
    body = f"""<main class="shell"><div class="eyebrow">China Index Return Lab</div><h1>中国指数长期收益实验室</h1>
<p class="lead">比较中国宽基指数在不同起始年份和持有期限下的一次投入 CAGR、年度定投 IRR，以及二者的差值。当前统计区间为 {start_year}–{end_year} 年。</p>
<nav class="topnav"><a href="methodology.html">方法与数据说明</a><a href="assets/index.html">标的目录</a></nav>
<h2 class="section-title">投资标的</h2><div class="grid">{''.join(cards)}</div>
<div class="footer">数据来自中证指数，经 AkShare 获取。沪深300全收益指数包含已披露的2005年分红估算修正。历史收益不代表未来表现，不构成投资建议。</div></main>"""
    return page("中国指数长期收益实验室", body)


def methodology() -> str:
    body = """<main class="shell"><div class="eyebrow">Methodology</div><h1>方法与数据说明</h1>
<nav class="topnav"><a href="index.html">← 返回首页</a></nav><article class="prose">
<h2>一次投入</h2><p>在起始年份前一年度最后一个可用收盘点位投入并持有 N 年，以终止年度最后一个可用收盘点位估值。年化收益使用复合年化收益率：</p><p><code>CAGR = (终点指数 / 起点指数) ^ (1 / N) - 1</code></p>
<h2>年度定投</h2><p>每年年初等额投入一份，共投入 N 次，在第 N 年年末估值。年化收益使用等间隔年度现金流 IRR；累计收益以期末资产相对累计投入计算。</p>
<h2>差值</h2><p><code>定投 IRR − 一次投入 CAGR</code>。正数表示该历史区间内定投的年化收益更高，负数表示一次投入更高。</p>
<h2>数据与修正</h2><p>宽基指数使用全收益口径。H00300 在2005年公布的全收益点位与价格指数相同，缺少分红；本站按《中国大类资产投资 2025 年报》披露的方法，将2005年及以后财富序列乘以1.026，使2005年收益由约−7.65%修正为约−5.25%。</p>
<h2>限制</h2><p>指数历史数据、回溯数据和估算值可能与其他数据商存在差异。页面不计交易费用、税费、滑点和实际申赎约束，仅供研究，不构成投资建议。</p></article></main>"""
    return page("方法与数据说明｜中国指数长期收益实验室", body)


def build_asset_site(
    docs_dir: Path, asset: AssetDefinition, start_year: int, end_year: int
) -> None:
    asset_dir = docs_dir / "assets" / asset.key
    asset_dir.mkdir(parents=True, exist_ok=True)
    closes = fetch_csindex_closes(asset.symbol, start_year, end_year)
    annual = year_end_closes(closes)
    annual, adjustment_notes = apply_known_adjustments(annual, asset.symbol)
    lump, warnings = build_matrix(annual, start_year, end_year)
    if warnings:
        raise RuntimeError("；".join(warnings))
    dca, terminal_values = build_dca_matrices(annual, start_year, end_year)
    difference = dca - lump
    matrices = {"lump": lump, "dca": dca, "difference": difference}
    page_names = {report.mode: report.filename for report in REPORTS}

    for report in REPORTS:
        target = asset_dir / report.filename
        target.write_text(
            render_comparison_html(
                matrices[report.mode], lump, dca, difference, terminal_values,
                mode=report.mode, annual=annual, symbol=asset.symbol, name=asset.name,
                start_year=start_year, end_year=end_year,
                adjustment_notes=adjustment_notes, page_names=page_names,
                home_href="../../index.html",
            ),
            encoding="utf-8",
        )
        matrices[report.mode].to_csv(
            target.with_suffix(".csv"), encoding="utf-8-sig", float_format="%.4f"
        )

    full_period = end_year - start_year + 1
    (asset_dir / "index.html").write_text(
        asset_landing(
            asset, start_year, end_year,
            float(lump.at[full_period, start_year]),
            float(dca.at[full_period, start_year]),
            adjustment_notes,
        ),
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建 docs/ GitHub Pages 静态站点")
    parser.add_argument("--assets", default="all", help="逗号分隔的资产 key/code；默认 all")
    parser.add_argument("--list-assets", action="store_true")
    parser.add_argument("--start-year", type=int, default=2005)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--output-dir", type=Path, default=Path("docs"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.list_assets:
        print(asset_help())
        return 0
    selected = resolve_assets(args.assets)
    docs_dir = args.output_dir
    (docs_dir / "assets").mkdir(parents=True, exist_ok=True)
    (docs_dir / "assets" / "site.css").write_text(SITE_CSS.strip() + "\n", encoding="utf-8")
    (docs_dir / ".nojekyll").write_text("", encoding="utf-8")
    (docs_dir / "index.html").write_text(home(selected, args.start_year, args.end_year), encoding="utf-8")
    (docs_dir / "methodology.html").write_text(methodology(), encoding="utf-8")
    directory_links = "".join(
        f'<li><a href="{asset.key}/index.html">{html.escape(asset.category)} · {html.escape(asset.name)}（{asset.symbol}）</a></li>'
        for asset in selected
    )
    directory_body = f'<main class="shell"><h1>标的目录</h1><nav class="topnav"><a href="../index.html">← 返回首页</a></nav><div class="prose"><ul>{directory_links}</ul></div></main>'
    (docs_dir / "assets" / "index.html").write_text(
        page("标的目录｜中国指数长期收益实验室", directory_body, depth=1), encoding="utf-8"
    )
    for asset in selected:
        print(f"building {asset.key} ({asset.symbol})")
        build_asset_site(docs_dir, asset, args.start_year, args.end_year)
    print(f"site: {(docs_dir / 'index.html').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
