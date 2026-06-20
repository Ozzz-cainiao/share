#!/usr/bin/env python3
"""Compare lump-sum CAGR with equal annual contribution IRR."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

import numpy as np
import pandas as pd

from asset_catalog import AssetDefinition, asset_help, resolve_assets
from rolling_returns import (
    apply_known_adjustments,
    build_matrix,
    cell_style,
    fetch_asset_closes,
    source_label,
    year_end_closes,
)


def periodic_irr(cashflows: list[float]) -> float:
    """Return the annual IRR for equally spaced yearly cash flows."""
    if not cashflows or not any(value < 0 for value in cashflows) or not any(
        value > 0 for value in cashflows
    ):
        return float("nan")

    def npv(rate: float) -> float:
        return sum(value / (1.0 + rate) ** period for period, value in enumerate(cashflows))

    low, high = -0.999999, 1.0
    low_value, high_value = npv(low), npv(high)
    while low_value * high_value > 0 and high < 1_000_000:
        high = high * 2.0 + 1.0
        high_value = npv(high)
    if low_value * high_value > 0:
        return float("nan")

    for _ in range(200):
        middle = (low + high) / 2.0
        middle_value = npv(middle)
        if abs(middle_value) < 1e-12:
            return middle
        if low_value * middle_value <= 0:
            high, high_value = middle, middle_value
        else:
            low, low_value = middle, middle_value
    return (low + high) / 2.0


def build_dca_matrices(
    annual: pd.DataFrame, start_year: int, end_year: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build annual DCA IRR and terminal-value matrices.

    One unit is invested at each year start. For an N-year period there are N
    equal contributions, followed by liquidation at the end of year N.
    """
    starts = list(range(start_year, end_year + 1))
    periods = list(range(1, end_year - start_year + 2))
    irr = pd.DataFrame(index=periods, columns=starts, dtype=float)
    terminal_values = pd.DataFrame(index=periods, columns=starts, dtype=float)
    available = set(int(year) for year in annual.index)

    for start in starts:
        for years in periods:
            finish = start + years - 1
            contribution_years = list(range(start - 1, finish))
            if finish > end_year or finish not in available:
                continue
            if any(year not in available for year in contribution_years):
                continue
            terminal_price = float(annual.at[finish, "close"])
            shares = sum(1.0 / float(annual.at[year, "close"]) for year in contribution_years)
            terminal_value = shares * terminal_price
            cashflows = [-1.0] * years + [terminal_value]
            irr.at[years, start] = periodic_irr(cashflows) * 100.0
            terminal_values.at[years, start] = terminal_value
    return irr, terminal_values


def _scale(matrix: pd.DataFrame) -> float:
    values = matrix.to_numpy(dtype=float)
    finite = np.abs(values[np.isfinite(values)])
    return max(float(np.percentile(finite, 95)) if finite.size else 1.0, 1e-12)


def render_comparison_html(
    primary: pd.DataFrame,
    lump_sum: pd.DataFrame,
    dca: pd.DataFrame,
    difference: pd.DataFrame,
    terminal_values: pd.DataFrame,
    *,
    mode: str,
    annual: pd.DataFrame,
    symbol: str,
    name: str,
    start_year: int,
    end_year: int,
    adjustment_notes: list[str],
    page_names: dict[str, str] | None = None,
    home_href: str | None = None,
    source_text: str = "AkShare / 中证指数",
) -> str:
    page_names = page_names or {
        "lump": f"{symbol.lower()}_lump_sum_annualized_returns.html",
        "dca": f"{symbol.lower()}_dca_annualized_returns.html",
        "difference": f"{symbol.lower()}_dca_minus_lump_sum.html",
    }
    configs = {
        "lump": (
            "一次投入滚动年化收益率",
            "一次投入 CAGR",
            "起始年前一年度末一次性投入，并持有至终止年度末。",
            page_names["lump"],
        ),
        "dca": (
            "年度定投滚动年化收益率",
            "定投 IRR",
            "每年年初等额投入一份，共投入 N 次；在第 N 年年末估值，按年度 IRR 计算。",
            page_names["dca"],
        ),
        "difference": (
            "定投与一次投入的年化收益差",
            "定投 IRR − 一次投入 CAGR",
            "正数表示定投年化收益更高，负数表示一次投入年化收益更高。",
            page_names["difference"],
        ),
    }
    heading, metric_label, explanation, _ = configs[mode]
    scale = _scale(primary)
    poster_width = max(2100, 190 + len(primary.columns) * 91)
    header = "".join(f"<th>{year}</th>" for year in primary.columns)
    rows: list[str] = []

    for years, row in primary.iterrows():
        label = f"持有 {years} 年"
        if years == int(primary.index[-1]):
            label += f"<small>（至 {end_year} 年）</small>"
        cells: list[str] = []
        for start, value in row.items():
            if pd.isna(value):
                cells.append("<td></td>")
                continue
            finish = int(start) + int(years) - 1
            lump_value = float(lump_sum.at[years, start])
            dca_value = float(dca.at[years, start])
            diff_value = float(difference.at[years, start])
            terminal_value = float(terminal_values.at[years, start])
            lump_total_return = ((1.0 + lump_value / 100.0) ** int(years) - 1.0) * 100.0
            dca_total_return = (terminal_value / float(years) - 1.0) * 100.0
            cells.append(
                f'<td class="metric" tabindex="0" style="{cell_style(value, scale)}" '
                f'data-start="{int(start)}" data-finish="{finish}" data-years="{int(years)}" '
                f'data-lump="{lump_value:.4f}" data-lump-total="{lump_total_return:.4f}" '
                f'data-dca="{dca_value:.4f}" '
                f'data-diff="{diff_value:.4f}" data-terminal="{terminal_value:.4f}" '
                f'data-total-return="{dca_total_return:.4f}">{float(value):.2f}</td>'
            )
        rows.append(f'<tr><th scope="row">{label}</th>{"".join(cells)}</tr>')

    nav = "".join(
        f'<a class="{"active" if key == mode else ""}" href="{filename}">{label}</a>'
        for key, (_, label, _, filename) in configs.items()
    )
    csv_name = Path(page_names[mode]).with_suffix(".csv").name
    nav += f'<a href="{html.escape(csv_name)}" download>下载当前 CSV</a>'
    if home_href:
        nav = f'<a href="{html.escape(home_href)}">← 站点首页</a>' + nav
    title = f"{html.escape(name)}：{heading}（{start_year}–{end_year} 年）"
    first_date = pd.Timestamp(annual["date"].min()).date().isoformat()
    last_date = pd.Timestamp(annual["date"].max()).date().isoformat()
    coverage_text = (
        f"{start_year}–{end_year} 年度收益"
        if source_text.startswith("Total Real Returns")
        else f"{first_date} 至 {last_date}"
    )
    adjustment_html = ""
    if adjustment_notes:
        adjustment_html = '<div class="data-note">数据修正：' + html.escape(
            "；".join(adjustment_notes)
        ) + "</div>"

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--ink:#273249;--muted:#5d687c;--line:#dce2ed;--paper:#f8f9fd;--brand:#405477}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
main{{max-width:1540px;margin:auto;padding:30px 34px 42px}} h1{{font-family:Georgia,"Songti SC",serif;font-size:32px;font-weight:500;margin:0 0 18px}}
.nav{{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 20px}} .nav a{{padding:8px 13px;border:1px solid #ccd4e2;border-radius:8px;background:white;color:#53617a;text-decoration:none;font-size:14px}}
.nav a:hover,.nav a.active{{background:var(--brand);border-color:var(--brand);color:white}} .note{{color:var(--muted);font-size:16px;line-height:1.8;margin-bottom:22px}}
.data-note{{margin:-8px 0 18px;padding:10px 13px;border:1px solid #dfc578;border-radius:8px;background:#fff8dc;color:#665629;font-size:14px;line-height:1.6}}
.table-wrap{{overflow:auto;max-height:calc(100vh - 245px);border:1px solid var(--line);background:white;box-shadow:0 5px 20px rgba(30,42,68,.05)}}
table{{border-collapse:separate;border-spacing:0;min-width:max-content;width:100%;font-variant-numeric:tabular-nums}} th,td{{height:59px;min-width:91px;padding:10px 12px;text-align:center;border-right:1px solid var(--line);border-bottom:1px solid var(--line);font-size:17px;white-space:nowrap}}
thead th{{position:sticky;top:0;z-index:3;background:#f3f5fa}} th:first-child{{position:sticky;left:0;z-index:4;min-width:147px;background:#fff}} thead th:first-child{{background:#f3f5fa;z-index:5}}
tr:nth-child(5n) th,tr:nth-child(5n) td{{border-bottom-color:#71809a}} small{{display:block;font-size:12px;color:#687287}}
.metric{{cursor:crosshair}} .metric:hover,.metric:focus,.metric.pinned{{filter:saturate(1.16) brightness(.97);outline:2px solid #34415d;outline-offset:-2px}}
.tooltip{{position:fixed;display:none;z-index:20;min-width:290px;padding:15px 17px;border-radius:11px;background:rgba(25,34,52,.97);color:white;box-shadow:0 12px 34px rgba(14,22,40,.28);pointer-events:none;font-variant-numeric:tabular-nums}} .tooltip.show{{display:block}}
.tooltip strong{{display:block;margin-bottom:10px}} .grid{{display:grid;grid-template-columns:auto auto;gap:6px 18px;font-size:14px}} .grid span:nth-child(odd){{color:#bac5d9}} .grid span:nth-child(even){{text-align:right;font-weight:600}}
.hint{{margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,.16);color:#aebbd1;font-size:12px}} .source{{margin:18px 8px 0;color:#7b8497;font-size:13px}}
.source a{{color:rgb(83,106,145)}} .brand-footer{{margin:12px 8px 0;color:rgb(83,97,122);font-size:14px;font-weight:600}}
body.poster{{position:relative;overflow:hidden}} body.poster main{{width:{poster_width}px;max-width:none;padding:34px 26px 42px}} body.poster .table-wrap{{max-height:none;overflow:visible}} body.poster .nav{{display:none}}
.watermark-layer{{position:absolute;inset:140px 0 0;z-index:6;display:grid;grid-template-columns:repeat(5,1fr);grid-template-rows:repeat(12,1fr);align-items:center;justify-items:center;overflow:hidden;pointer-events:none;color:rgba(40,57,84,.13);font-size:25px;font-weight:700;letter-spacing:.08em}} .watermark-layer span{{white-space:nowrap;transform:rotate(-16deg)}}
@media(max-width:700px){{main{{padding:20px 14px}}h1{{font-size:24px}}th,td{{min-width:78px;height:52px;font-size:15px}}}}
</style></head><body><main>
<h1>{title}</h1><nav class="nav">{nav}</nav>
<div class="note">当前单元格指标：<strong>{metric_label}</strong>。{explanation}<br>鼠标悬浮可同时查看一次投入、定投及差值；点击可固定信息卡。</div>
{adjustment_html}
<div class="table-wrap"><table><thead><tr><th>起始年份</th>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<div class="source">数据来源：{html.escape(source_text)}；标的：{html.escape(name)}（{html.escape(symbol)}）；数据覆盖 {coverage_text}。参考资料：<a href="https://youzhiyouxing.cn/sbbi2025/annual-rolling-returns/" target="_blank" rel="noopener">有知有行《中国大类资产投资2025年报》滚动年化收益</a>。</div>
<div class="brand-footer">更多长期投资研究，欢迎关注公众号：炼金魔女手记</div>
<div id="tooltip" class="tooltip" role="status" aria-live="polite"></div>
</main><script>
if(new URLSearchParams(location.search).get("poster")==="1"){{
  document.body.classList.add("poster");
  const watermark=document.createElement("div");
  watermark.className="watermark-layer";
  watermark.setAttribute("aria-hidden","true");
  watermark.innerHTML=Array.from({{length:60}},()=>"<span>炼金魔女手记</span>").join("");
  document.body.prepend(watermark);
}}
const tip=document.getElementById("tooltip"),cells=document.querySelectorAll("td.metric");let pinned=null;
const signed=v=>`${{Number(v)>=0?"+":""}}${{Number(v).toFixed(2)}}%`;
function fill(c){{const d=c.dataset;tip.innerHTML=`<strong>${{d.start}}–${{d.finish}} · 持有 ${{d.years}} 年</strong><div class="grid"><span>一次投入 CAGR</span><span>${{signed(d.lump)}}</span><span>一次投入累计收益</span><span>${{signed(d.lumpTotal)}}</span><span>定投 IRR</span><span>${{signed(d.dca)}}</span><span>定投 − 一次投入</span><span>${{signed(d.diff)}}</span><span>定投累计投入</span><span>${{Number(d.years).toFixed(0)}} 份</span><span>定投期末资产</span><span>${{Number(d.terminal).toFixed(2)}} 份</span><span>定投累计收益</span><span>${{signed(d.totalReturn)}}</span></div><div class="hint">点击单元格可固定 / 取消固定</div>`}}
function place(x,y){{const g=16;tip.style.left=`${{Math.max(10,Math.min(x+g,innerWidth-tip.offsetWidth-10))}}px`;tip.style.top=`${{Math.max(10,Math.min(y+g,innerHeight-tip.offsetHeight-10))}}px`}}
function show(c,x,y){{fill(c);tip.classList.add("show");place(x,y)}}
cells.forEach(c=>{{c.addEventListener("mouseenter",e=>{{if(!pinned)show(c,e.clientX,e.clientY)}});c.addEventListener("mousemove",e=>{{if(!pinned)place(e.clientX,e.clientY)}});c.addEventListener("mouseleave",()=>{{if(!pinned)tip.classList.remove("show")}});c.addEventListener("focus",()=>{{if(!pinned){{const r=c.getBoundingClientRect();show(c,r.right,r.top)}}}});c.addEventListener("blur",()=>{{if(!pinned)tip.classList.remove("show")}});c.addEventListener("click",e=>{{e.stopPropagation();if(pinned===c){{c.classList.remove("pinned");pinned=null;tip.classList.remove("show");return}}if(pinned)pinned.classList.remove("pinned");pinned=c;c.classList.add("pinned");const r=c.getBoundingClientRect();show(c,r.right,r.top)}})}});
document.addEventListener("click",()=>{{if(pinned)pinned.classList.remove("pinned");pinned=null;tip.classList.remove("show")}});
</script></body></html>"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="比较一次投入 CAGR 与年度定投 IRR")
    parser.add_argument("--start-year", type=int, default=None, help="覆盖标的默认起始年份")
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument(
        "--assets",
        default="all-a",
        help="逗号分隔的标的 key 或指数代码；使用 all 生成全部内置标的",
    )
    parser.add_argument("--list-assets", action="store_true", help="列出内置投资标的后退出")
    parser.add_argument("--symbol", default=None, help="自定义中证指数代码（覆盖 --assets）")
    parser.add_argument("--name", default=None, help="自定义指数显示名称，与 --symbol 配合")
    parser.add_argument("--output-dir", type=Path, default=Path("output/dca_comparison"))
    parser.add_argument(
        "--no-known-adjustments",
        action="store_true",
        help="关闭已知的数据质量修正，使用数据源原始点位",
    )
    return parser.parse_args()


def run_asset(args: argparse.Namespace, asset: AssetDefinition) -> dict[str, str]:
    start_year = args.start_year if args.start_year is not None else asset.start_year
    closes = fetch_asset_closes(asset, start_year, args.end_year)
    annual = year_end_closes(closes)
    adjustment_notes: list[str] = []
    if not args.no_known_adjustments:
        annual, adjustment_notes = apply_known_adjustments(annual, asset.symbol)
    lump_sum, warnings = build_matrix(annual, start_year, args.end_year)
    if warnings:
        raise RuntimeError("；".join(warnings))
    dca, terminal_values = build_dca_matrices(annual, start_year, args.end_year)
    difference = dca - lump_sum
    slug = asset.symbol.lower()

    outputs = {
        "lump": (lump_sum, f"{slug}_lump_sum_annualized_returns.html"),
        "dca": (dca, f"{slug}_dca_annualized_returns.html"),
        "difference": (difference, f"{slug}_dca_minus_lump_sum.html"),
    }
    links: dict[str, str] = {}
    for mode, (matrix, filename) in outputs.items():
        path = args.output_dir / filename
        path.write_text(
            render_comparison_html(
                matrix, lump_sum, dca, difference, terminal_values,
                mode=mode, annual=annual, symbol=asset.symbol, name=asset.name,
                start_year=start_year, end_year=args.end_year,
                adjustment_notes=adjustment_notes,
                source_text=source_label(asset),
            ),
            encoding="utf-8",
        )
        matrix.to_csv(path.with_suffix(".csv"), encoding="utf-8-sig", float_format="%.4f")
        print(f"{mode}: {path.resolve()}")
        links[mode] = filename
    return links


def render_asset_index(
    results: list[tuple[AssetDefinition, dict[str, str]]], end_year: int
) -> str:
    cards = []
    for asset, links in results:
        adjustment = (
            '<span class="badge">含2005分红修正</span>' if asset.symbol == "H00300" else ""
        )
        cards.append(
            f'<article><div class="category">{html.escape(asset.category)}</div>'
            f'<h2>{html.escape(asset.name)}</h2><div class="code">{asset.symbol}</div>{adjustment}'
            f'<nav><a href="{links["lump"]}">一次投入</a>'
            f'<a href="{links["dca"]}">年度定投</a>'
            f'<a href="{links["difference"]}">收益差值</a></nav></article>'
        )
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>投资标的收益对比</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#f5f7fb;color:#273249;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif}}main{{max-width:1080px;margin:auto;padding:42px 28px}}h1{{margin:0 0 8px;font:600 32px Georgia,"Songti SC",serif}}.intro{{color:#69758a;margin-bottom:28px}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(285px,1fr));gap:18px}}article{{position:relative;padding:22px;border:1px solid #dce2ed;border-radius:14px;background:white;box-shadow:0 8px 28px rgba(35,45,75,.06)}}.category{{color:#77839a;font-size:13px}}h2{{margin:7px 0 5px;font-size:21px}}.code{{color:#8a94a7;font-family:ui-monospace,monospace}}.badge{{display:inline-block;margin-top:10px;padding:3px 8px;border-radius:12px;background:#fff1c7;color:#795d13;font-size:12px}}nav{{display:flex;gap:8px;margin-top:20px;flex-wrap:wrap}}a{{padding:8px 11px;border-radius:8px;background:#405477;color:white;text-decoration:none;font-size:14px}}a:hover{{background:#2f405f}}</style></head><body><main>
<h1>投资标的收益对比</h1><p class="intro">各标的按默认历史起点统计至 {end_year} 年 · 选择标的与分析方式</p>
<div class="grid">{''.join(cards)}</div></main></body></html>"""


def main() -> int:
    args = parse_args()
    if args.list_assets:
        print(asset_help())
        return 0
    if args.start_year is not None and args.start_year > args.end_year:
        raise SystemExit("--start-year 不能晚于 --end-year")
    if args.symbol:
        selected = [
            AssetDefinition("custom", args.symbol.upper(), args.name or args.symbol.upper(), "自定义标的")
        ]
    else:
        try:
            selected = resolve_assets(args.assets)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = [(asset, run_asset(args, asset)) for asset in selected]
    index_path = args.output_dir / "index.html"
    index_path.write_text(
        render_asset_index(results, args.end_year), encoding="utf-8"
    )
    print(f"index: {index_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
