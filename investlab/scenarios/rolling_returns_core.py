from __future__ import annotations

import argparse
import html
import re
import sys
from io import StringIO

import akshare as ak
import numpy as np
import pandas as pd
import requests

from asset_catalog import AssetDefinition, resolve_assets
from investlab.core.price_loading import fetch_fred_closes, fetch_yahoo_index_closes
from investlab.scenarios.annual_matrix import (
    apply_known_adjustments,
    build_matrix,
    year_end_closes,
)


def fetch_csindex_closes(symbol: str, start_year: int, end_year: int) -> pd.Series:
    """Fetch and normalize daily closes from AkShare's CSI index endpoint."""
    raw = ak.stock_zh_index_hist_csindex(
        symbol=symbol,
        start_date=f"{start_year - 1}0101",
        end_date=f"{end_year}1231",
    )
    if raw is None or raw.empty:
        raise RuntimeError(f"AkShare 未返回 {symbol} 的数据")

    date_col = next((c for c in ("日期", "date", "Date") if c in raw.columns), None)
    close_col = next((c for c in ("收盘", "close", "Close") if c in raw.columns), None)
    if date_col is None or close_col is None:
        raise RuntimeError(f"无法识别日期/收盘列；实际列名：{list(raw.columns)}")

    dates = pd.to_datetime(raw[date_col], errors="coerce")
    values = pd.to_numeric(raw[close_col], errors="coerce")
    closes = pd.Series(values.to_numpy(), index=dates, name=symbol)
    closes = closes[~closes.index.isna()].dropna().sort_index()
    closes = closes[~closes.index.duplicated(keep="last")]
    closes = closes[closes > 0]
    if closes.empty:
        raise RuntimeError(f"{symbol} 没有可用的正数收盘价")
    return closes


def fetch_us_etf_closes(symbol: str, start_year: int, end_year: int) -> pd.Series:
    response = requests.get(
        f"https://totalrealreturns.com/n/{symbol}",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    tables = pd.read_html(StringIO(response.content.decode("utf-8")))
    annual = next(
        (
            table
            for table in tables
            if "Year" in table.columns and symbol in table.columns
        ),
        None,
    )
    if annual is None:
        raise RuntimeError(f"无法识别 {symbol} 的年度总收益表")

    years = annual["Year"].astype(str).str.extract(r"(\d{4})", expand=False)
    values = (
        annual[symbol]
        .astype(str)
        .str.replace("−", "-", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("+", "", regex=False)
    )
    returns = pd.Series(
        pd.to_numeric(values, errors="coerce").to_numpy(),
        index=pd.to_numeric(years, errors="coerce"),
    ).dropna()
    returns.index = returns.index.astype(int)

    required = set(range(start_year, end_year + 1))
    missing = sorted(required - set(returns.index))
    if missing:
        raise RuntimeError(f"{symbol} 缺少年度总收益：{missing}")

    wealth = {start_year - 1: 100.0}
    for year in range(start_year, end_year + 1):
        wealth[year] = wealth[year - 1] * (1.0 + float(returns.at[year]) / 100.0)
    dates = pd.to_datetime([f"{year}-12-31" for year in wealth])
    return pd.Series(list(wealth.values()), index=dates, name=symbol)


def fetch_asset_closes(
    asset: AssetDefinition, start_year: int, end_year: int
) -> pd.Series:
    match asset.source:
        case "csindex":
            return fetch_csindex_closes(asset.symbol, start_year, end_year)
        case "us_etf_total_return":
            return fetch_us_etf_closes(asset.symbol, start_year, end_year)
        case "fred":
            return fetch_fred_closes(asset.symbol, start_year, end_year)
        case "yahoo_index":
            return fetch_yahoo_index_closes(asset.symbol, start_year, end_year)
        case _:
            raise ValueError(f"不支持的数据源：{asset.source}")


def source_label(asset: AssetDefinition) -> str:
    match asset.source:
        case "us_etf_total_return":
            return "Total Real Returns / ETF 分红再投资年度总收益"
        case "fred":
            return "FRED（美联储经济数据）/ 纳斯达克100全收益指数（XNDX，含股息）"
        case "yahoo_index":
            return "Yahoo Finance / 纳斯达克100指数（^NDX 价格指数，不含股息）"
        case _:
            return "AkShare / 中证指数"


def cell_style(value: float, scale: float) -> str:
    if pd.isna(value):
        return ""
    strength = min(abs(float(value)) / scale, 1.0) if scale > 0 else 0.0
    # Keep small changes visible while allowing extreme observations to stand out.
    alpha = 0.08 + 0.84 * (strength**0.72)
    rgb = "190, 0, 0" if value >= 0 else "30, 150, 135"
    color = "#ffffff" if strength >= 0.66 else "#202b3c"
    return f"background:rgba({rgb},{alpha:.3f});color:{color}"


def render_html(
    matrix: pd.DataFrame,
    annual: pd.DataFrame,
    symbol: str,
    name: str,
    start_year: int,
    end_year: int,
    warnings: list[str],
    source_text: str = "AkShare / 中证指数",
) -> str:
    values = matrix.to_numpy(dtype=float)
    finite_abs = np.abs(values[np.isfinite(values)])
    # A robust scale prevents one crisis/bull-market outlier flattening every cell.
    scale = float(np.percentile(finite_abs, 95)) if finite_abs.size else 1.0
    scale = max(scale, 1e-12)

    head = "".join(f"<th>{year}</th>" for year in matrix.columns)
    rows: list[str] = []
    last_period = int(matrix.index[-1])
    for period, row in matrix.iterrows():
        label = f"持有 {period} 年"
        if period == last_period:
            label += f"<small>（至 {end_year} 年）</small>"
        cells = []
        for start, value in row.items():
            if pd.isna(value):
                cells.append("<td></td>")
                continue
            finish = int(start) + int(period) - 1
            base = float(annual.at[int(start) - 1, "close"])
            terminal = float(annual.at[finish, "close"])
            cumulative = (terminal / base - 1.0) * 100.0
            cells.append(
                f'<td class="metric" tabindex="0" style="{cell_style(value, scale)}" '
                f'data-start="{int(start)}" data-finish="{finish}" data-years="{int(period)}" '
                f'data-cagr="{float(value):.4f}" data-total="{cumulative:.4f}" '
                f'data-base="{base:.4f}" data-terminal="{terminal:.4f}">{float(value):.2f}</td>'
            )
        rows.append(f'<tr><th scope="row">{label}</th>{"".join(cells)}</tr>')

    warning_html = ""
    if warnings:
        warning_html = '<div class="warning">数据提示：' + html.escape("；".join(warnings)) + "</div>"
    first_date = pd.Timestamp(annual["date"].min()).date().isoformat()
    last_date = pd.Timestamp(annual["date"].max()).date().isoformat()
    coverage_text = (
        f"{start_year}–{end_year} 年度收益"
        if source_text.startswith("Total Real Returns")
        else f"{first_date} 至 {last_date}"
    )
    safe_name, safe_symbol = html.escape(name), html.escape(symbol)
    title = f"{safe_name}的滚动年化收益率（{start_year}–{end_year} 年）"
    poster_width = max(2100, 190 + len(matrix.columns) * 91)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
:root{{--ink:#273249;--muted:#5d687c;--line:#dce2ed;--paper:#f8f9fd}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
main{{max-width:1540px;margin:0 auto;padding:30px 34px 42px}}
h1{{font-family:Georgia,"Songti SC","SimSun",serif;font-size:34px;font-weight:500;margin:0 0 22px}}
.note{{color:var(--muted);font-size:17px;line-height:1.9;margin-bottom:24px}}
.warning{{padding:10px 14px;margin:0 0 16px;background:#fff2cc;border:1px solid #e6ca75;border-radius:5px}}
.table-wrap{{overflow-x:auto;border:1px solid var(--line);background:white;box-shadow:0 2px 10px rgba(30,42,68,.03)}}
table{{border-collapse:separate;border-spacing:0;min-width:max-content;width:100%;font-variant-numeric:tabular-nums}}
th,td{{height:59px;min-width:91px;padding:10px 12px;text-align:center;border-right:1px solid var(--line);border-bottom:1px solid var(--line);font-size:17px;white-space:nowrap}}
thead th{{position:sticky;top:0;z-index:2;background:#f3f5fa;font-weight:600}}
th:first-child{{position:sticky;left:0;z-index:3;min-width:147px;background:#fff;font-weight:600}}
thead th:first-child{{background:#f3f5fa;z-index:4}}
tr:nth-child(5n) th,tr:nth-child(5n) td{{border-bottom-color:#71809a}}
small{{display:block;font-size:12px;color:#687287;margin-top:3px}}
.source{{color:#7b8497;font-size:14px;margin:20px 10px 0}}
.metric{{cursor:crosshair;transition:filter .12s ease,outline-color .12s ease}}
.metric:hover,.metric:focus,.metric.pinned{{filter:saturate(1.16) brightness(.97);outline:2px solid #34415d;outline-offset:-2px}}
.tooltip{{position:fixed;display:none;z-index:20;min-width:265px;padding:14px 16px;border:1px solid rgba(82,96,125,.25);border-radius:10px;background:rgba(25,34,52,.96);color:#fff;box-shadow:0 12px 34px rgba(14,22,40,.26);pointer-events:none;backdrop-filter:blur(8px);font-variant-numeric:tabular-nums}}
.tooltip.show{{display:block}}
.tooltip strong{{display:block;margin-bottom:10px;font-size:16px}}
.tooltip-grid{{display:grid;grid-template-columns:auto auto;gap:6px 18px;font-size:14px}}
.tooltip-grid span:nth-child(odd){{color:#bac5d9}}
.tooltip-grid span:nth-child(even){{text-align:right;font-weight:600}}
.tooltip .hint{{margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,.16);color:#aebbd1;font-size:12px}}
.source a{{color:rgb(83,106,145)}} .brand-footer{{color:rgb(83,97,122);font-size:14px;font-weight:600;margin:12px 10px 0}}
body.poster{{position:relative;overflow:hidden}} body.poster main{{width:{poster_width}px;max-width:none;padding:34px 26px 42px}} body.poster .table-wrap{{overflow:visible}}
.watermark-layer{{position:absolute;inset:140px 0 0;z-index:6;display:grid;grid-template-columns:repeat(5,1fr);grid-template-rows:repeat(12,1fr);align-items:center;justify-items:center;overflow:hidden;pointer-events:none;color:rgba(40,57,84,.13);font-size:25px;font-weight:700;letter-spacing:.08em}} .watermark-layer span{{white-space:nowrap;transform:rotate(-16deg)}}
@media(max-width:700px){{main{{padding:20px 14px}}h1{{font-size:25px}}th,td{{min-width:78px;height:52px;font-size:15px}}}}
</style>
</head>
<body><main>
<h1>图 2-1 {title}</h1>
<div class="note">表格中的数据均为百分数（单位：%）；<br>表格背景色越深代表收益率绝对值越大，红色为正收益，绿色为负收益。持有 N 年按复合年化收益率（CAGR）计算。将鼠标悬浮在单元格上可查看完整区间信息，点击可固定信息卡。</div>
{warning_html}
<div class="table-wrap"><table>
<thead><tr><th>起始年份</th>{head}</tr></thead>
<tbody>{''.join(rows)}</tbody>
</table></div>
<div class="source">数据来源：{html.escape(source_text)}；标的：{safe_name}（{safe_symbol}）；数据覆盖 {coverage_text}。计算口径：起始年前一年度最后可用收盘至终止年度最后可用收盘。参考资料：<a href="https://youzhiyouxing.cn/sbbi2025/annual-rolling-returns/" target="_blank" rel="noopener">有知有行《中国大类资产投资2025年报》滚动年化收益</a>。</div>
<div class="brand-footer">更多长期投资研究，欢迎关注公众号：炼金魔女手记</div>
<div id="tooltip" class="tooltip" role="status" aria-live="polite"></div>
</main>
<script>
if(new URLSearchParams(location.search).get("poster")==="1"){{
  document.body.classList.add("poster");
  const watermark=document.createElement("div");
  watermark.className="watermark-layer";
  watermark.setAttribute("aria-hidden","true");
  watermark.innerHTML=Array.from({{length:60}},()=>"<span>炼金魔女手记</span>").join("");
  document.body.prepend(watermark);
}}
const tooltip = document.getElementById("tooltip");
const cells = document.querySelectorAll("td.metric");
let pinned = null;

function signed(value) {{
  const number = Number(value);
  return `${{number >= 0 ? "+" : ""}}${{number.toFixed(2)}}%`;
}}

function fillTooltip(cell) {{
  const d = cell.dataset;
  tooltip.innerHTML = `<strong>${{d.start}}–${{d.finish}} · 持有 ${{d.years}} 年</strong>
    <div class="tooltip-grid">
      <span>复合年化收益</span><span>${{signed(d.cagr)}}</span>
      <span>区间累计收益</span><span>${{signed(d.total)}}</span>
      <span>起点指数</span><span>${{Number(d.base).toLocaleString("zh-CN", {{maximumFractionDigits:2}})}}</span>
      <span>终点指数</span><span>${{Number(d.terminal).toLocaleString("zh-CN", {{maximumFractionDigits:2}})}}</span>
    </div><div class="hint">点击单元格可固定 / 取消固定</div>`;
}}

function positionTooltip(clientX, clientY) {{
  const gap = 16;
  const width = tooltip.offsetWidth;
  const height = tooltip.offsetHeight;
  const left = Math.min(clientX + gap, window.innerWidth - width - 10);
  const top = Math.min(clientY + gap, window.innerHeight - height - 10);
  tooltip.style.left = `${{Math.max(10, left)}}px`;
  tooltip.style.top = `${{Math.max(10, top)}}px`;
}}

function showAtCell(cell) {{
  fillTooltip(cell);
  tooltip.classList.add("show");
  const rect = cell.getBoundingClientRect();
  positionTooltip(rect.right, rect.top);
}}

cells.forEach(cell => {{
  cell.addEventListener("mouseenter", event => {{
    if (pinned) return;
    fillTooltip(cell);
    tooltip.classList.add("show");
    positionTooltip(event.clientX, event.clientY);
  }});
  cell.addEventListener("mousemove", event => {{
    if (!pinned) positionTooltip(event.clientX, event.clientY);
  }});
  cell.addEventListener("mouseleave", () => {{
    if (!pinned) tooltip.classList.remove("show");
  }});
  cell.addEventListener("focus", () => {{ if (!pinned) showAtCell(cell); }});
  cell.addEventListener("blur", () => {{ if (!pinned) tooltip.classList.remove("show"); }});
  cell.addEventListener("click", event => {{
    event.stopPropagation();
    if (pinned === cell) {{
      cell.classList.remove("pinned");
      pinned = null;
      tooltip.classList.remove("show");
      return;
    }}
    if (pinned) pinned.classList.remove("pinned");
    pinned = cell;
    cell.classList.add("pinned");
    showAtCell(cell);
  }});
}});

document.addEventListener("click", () => {{
  if (pinned) pinned.classList.remove("pinned");
  pinned = null;
  tooltip.classList.remove("show");
}});
</script>
</body></html>"""


def run_asset(args: argparse.Namespace, asset: AssetDefinition) -> str:
    start_year = args.start_year if args.start_year is not None else asset.start_year
    closes = fetch_asset_closes(asset, start_year, args.end_year)
    annual = year_end_closes(closes)
    adjustment_notes: list[str] = []
    if not args.no_known_adjustments:
        annual, adjustment_notes = apply_known_adjustments(annual, asset.symbol)
    matrix, warnings = build_matrix(annual, start_year, args.end_year)
    warnings = adjustment_notes + warnings

    slug = re.sub(r"[^a-z0-9]", "", asset.symbol.lower()) or asset.key
    csv_path = args.output_dir / f"{slug}_rolling_annualized_returns.csv"
    html_path = args.output_dir / f"{slug}_rolling_annualized_returns.html"
    csv_frame = matrix.copy()
    csv_frame.index = [f"持有 {years} 年" for years in matrix.index]
    csv_frame.index.name = "起始年份"
    csv_frame.to_csv(csv_path, encoding="utf-8-sig", float_format="%.2f")
    html_path.write_text(
        render_html(
            matrix, annual, asset.symbol, asset.name,
            start_year, args.end_year, warnings, source_label(asset),
        ),
        encoding="utf-8",
    )

    print(f"CSV:  {csv_path.resolve()}")
    print(f"HTML: {html_path.resolve()}")
    for warning in warnings:
        print(f"警告: {warning}", file=sys.stderr)
    return html_path.name


def run_with_args(args: argparse.Namespace) -> int:
    if args.start_year is not None and args.start_year > args.end_year:
        raise SystemExit("--start-year 不能晚于 --end-year")
    if (args.start_year is not None and args.start_year < 1990) or args.end_year > 2100:
        raise SystemExit("年份范围看起来不合理")
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
    links = [(asset, run_asset(args, asset)) for asset in selected]
    items = "".join(
        f'<li><a href="{filename}">{html.escape(asset.category)} · '
        f'{html.escape(asset.name)}（{asset.symbol}）</a></li>'
        for asset, filename in links
    )
    (args.output_dir / "index.html").write_text(
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>滚动年化收益率</title><style>body{max-width:760px;margin:48px auto;'
        'padding:0 24px;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;'
        'color:#273249}li{margin:12px 0}a{color:#405477}</style>'
        f'<h1>滚动年化收益率</h1><p>各标的按默认历史起点统计至 {args.end_year} 年</p><ul>{items}</ul>',
        encoding="utf-8",
    )
    return 0
