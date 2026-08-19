from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class IndexSpec:
    key: str
    name: str
    code: str
    launch_date: date
    source: str = "csindex"


@dataclass(frozen=True)
class IndexReturns:
    spec: IndexSpec
    dates: tuple[date, ...]
    returns: tuple[float, ...]

    @property
    def latest_date(self) -> date:
        return self.dates[-1]


INDEX_SPECS: tuple[IndexSpec, ...] = (
    IndexSpec("csi300", "沪深300", "000300", date(2005, 4, 8)),
    IndexSpec("csi500", "中证500", "000905", date(2007, 1, 15)),
    IndexSpec("csi800", "中证800", "000906", date(2007, 1, 15)),
    IndexSpec("csi1000", "中证1000", "000852", date(2014, 10, 17)),
    IndexSpec("a500", "中证A500", "000510", date(2024, 9, 23)),
    IndexSpec("chinext", "创业板指", "399006", date(2010, 6, 1), "sohu"),
    IndexSpec("star50", "科创50", "000688", date(2020, 7, 23)),
    IndexSpec("star100", "科创100", "000698", date(2023, 8, 7)),
    IndexSpec("star_chinext50", "科创创业50", "931643", date(2021, 6, 1)),
)


def _request_bytes(url: str, *, attempts: int = 5, timeout: int = 45) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/124 Safari/537.36"
            ),
            "Accept": "application/json,text/plain,*/*",
        },
    )
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:  # network retry boundary
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(2**attempt)
    raise RuntimeError(f"行情请求失败：{url}") from last_error


def fetch_csindex(spec: IndexSpec, end_date: date) -> IndexReturns:
    params = urlencode(
        {
            "indexCode": spec.code,
            "startDate": spec.launch_date.strftime("%Y%m%d"),
            "endDate": end_date.strftime("%Y%m%d"),
        }
    )
    payload = json.loads(
        _request_bytes(
            f"https://www.csindex.com.cn/csindex-home/perf/index-perf?{params}"
        ).decode("utf-8")
    )
    if payload.get("code") != "200" or not payload.get("success"):
        raise RuntimeError(f"中证指数接口返回异常：{spec.name} {payload.get('msg')}")
    observations: dict[date, float] = {}
    for row in payload.get("data") or []:
        trade_date = datetime.strptime(row["tradeDate"], "%Y%m%d").date()
        value = row.get("changePct")
        if trade_date >= spec.launch_date and value is not None:
            observations[trade_date] = float(value)
    return _validated_returns(spec, observations)


def fetch_sohu(spec: IndexSpec, end_date: date) -> IndexReturns:
    params = urlencode(
        {
            "code": f"zs_{spec.code}",
            "start": spec.launch_date.strftime("%Y%m%d"),
            "end": end_date.strftime("%Y%m%d"),
            "stat": "1",
            "order": "D",
            "period": "d",
            "callback": "historySearchHandler",
            "rt": "jsonp",
        }
    )
    text = _request_bytes(f"https://q.stock.sohu.com/hisHq?{params}").decode(
        "gb18030"
    )
    start = text.find("(")
    end = text.rfind(")")
    if start < 0 or end <= start:
        raise RuntimeError(f"搜狐行情接口返回异常：{spec.name}")
    payload = json.loads(text[start + 1 : end])
    item = payload[0]
    if item.get("status") != 0:
        raise RuntimeError(f"搜狐行情接口无数据：{spec.name}")
    observations: dict[date, float] = {}
    for row in item.get("hq") or []:
        trade_date = datetime.strptime(row[0], "%Y-%m-%d").date()
        pct = row[4].strip().rstrip("%")
        if trade_date >= spec.launch_date and pct:
            observations[trade_date] = float(pct)
    return _validated_returns(spec, observations)


def _validated_returns(
    spec: IndexSpec, observations: dict[date, float]
) -> IndexReturns:
    ordered = sorted(observations.items())
    if len(ordered) < 50:
        raise RuntimeError(f"{spec.name} 有效交易日不足：{len(ordered)}")
    dates = tuple(item[0] for item in ordered)
    values = tuple(item[1] for item in ordered)
    if any(not math.isfinite(value) for value in values):
        raise RuntimeError(f"{spec.name} 包含非有限涨跌幅")
    if dates[0] < spec.launch_date:
        raise RuntimeError(f"{spec.name} 数据早于正式发布日期")
    return IndexReturns(spec, dates, values)


def fetch_all(end_date: date) -> list[IndexReturns]:
    datasets: list[IndexReturns] = []
    for spec in INDEX_SPECS:
        fetcher = fetch_csindex if spec.source == "csindex" else fetch_sohu
        print(f"fetching {spec.name} ({spec.code})")
        datasets.append(fetcher(spec, end_date))
        time.sleep(0.8)
    return datasets


def _bin_dataset(
    dataset: IndexReturns, domain_min: int, domain_max: int
) -> list[dict[str, float | int]]:
    width = domain_max - domain_min
    counts = [0] * width
    for value in dataset.returns:
        index = math.floor(value) - domain_min
        index = max(0, min(width - 1, index))
        counts[index] += 1
    total = len(dataset.returns)
    return [
        {
            "x0": domain_min + index,
            "x1": domain_min + index + 1,
            "count": count,
            "share": round(count / total * 100, 4),
        }
        for index, count in enumerate(counts)
    ]


def build_payload(datasets: Iterable[IndexReturns]) -> dict[str, object]:
    values = list(datasets)
    if not values:
        raise ValueError("datasets must not be empty")
    global_min = min(min(item.returns) for item in values)
    global_max = max(max(item.returns) for item in values)
    domain_min = math.floor(global_min)
    domain_max = math.ceil(global_max)
    if domain_max <= domain_min:
        domain_max = domain_min + 1
    series = []
    for item in values:
        series.append(
            {
                "key": item.spec.key,
                "name": item.spec.name,
                "code": item.spec.code,
                "launchDate": item.spec.launch_date.isoformat(),
                "latestDate": item.latest_date.isoformat(),
                "count": len(item.returns),
                "mean": round(statistics.fmean(item.returns), 4),
                "median": round(statistics.median(item.returns), 4),
                "stdev": round(statistics.stdev(item.returns), 4),
                "min": min(item.returns),
                "max": max(item.returns),
                "bins": _bin_dataset(item, domain_min, domain_max),
            }
        )
    return {
        "domain": [domain_min, domain_max],
        "binWidth": 1,
        "latestDate": max(item.latest_date for item in values).isoformat(),
        "series": series,
    }


def render_page(payload: dict[str, object]) -> str:
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="九个A股宽基与成长指数正式发布以来的每日涨跌幅区间分布">
<title>每日涨跌幅分布｜中美指数长期收益实验室</title>
<style>
:root{{--ink:#26304a;--muted:#68758b;--line:#dce2ed;--paper:#f5f7fb;--brand:#405477;--card:#fff;--blue:#5279ad;--orange:#c67c4a;--grid:#e7ebf2}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
a{{color:inherit}}.shell{{max-width:1240px;margin:auto;padding:42px 26px 60px}}.eyebrow{{color:#7b879b;font-size:13px;letter-spacing:.08em;text-transform:uppercase}}
h1{{margin:8px 0 10px;font:600 38px Georgia,"Songti SC",serif}}.lead{{max-width:850px;margin:0;color:var(--muted);font-size:16px;line-height:1.75}}
.topnav{{display:flex;gap:10px;flex-wrap:wrap;margin:22px 0 26px}}.topnav a{{display:inline-block;padding:9px 13px;border-radius:9px;background:var(--brand);color:#fff;text-decoration:none;font-size:14px}}
.status{{display:flex;gap:18px;flex-wrap:wrap;padding:13px 16px;margin-bottom:22px;border:1px solid var(--line);background:#fff;border-radius:12px;color:var(--muted);font-size:13px}}.status strong{{color:var(--ink)}}
.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}}.panel{{min-width:0;padding:17px 16px 14px;border:1px solid var(--line);border-radius:14px;background:var(--card);box-shadow:0 7px 22px rgba(35,45,75,.045)}}
.panel-head{{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:2px}}.panel h2{{margin:0;font-size:18px}}.code{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#8791a3;font-size:12px}}.meta{{margin:4px 0 8px;color:var(--muted);font-size:12px;line-height:1.5}}
.chart{{position:relative;min-height:230px}}svg{{display:block;width:100%;height:auto}}svg text{{fill:var(--muted);font-size:10px}}.frame{{fill:transparent;stroke:var(--line)}}.gridline{{stroke:var(--grid)}}.zero{{stroke:var(--ink);stroke-dasharray:3 3;opacity:.6}}.bar{{fill:var(--blue)}}.panel:nth-child(3n+2) .bar{{fill:var(--orange)}}
.tooltip{{position:fixed;z-index:10;display:none;pointer-events:none;padding:8px 10px;border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink);font-size:12px;line-height:1.5;box-shadow:0 8px 22px rgba(35,45,75,.12)}}
.footer{{margin-top:36px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:13px;line-height:1.75}}
@media(max-width:980px){{.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:640px){{.shell{{padding:28px 14px 42px}}h1{{font-size:29px}}.grid{{grid-template-columns:1fr}}.status{{gap:8px 16px}}}}
</style>
</head>
<body><main class="shell">
<div class="eyebrow">Daily Return Distribution</div>
<h1>每日涨跌幅分布</h1>
<p class="lead">比较九个代表性A股指数自正式发布以来的单日涨跌幅。所有图使用相同横轴、纵轴和1个百分点分箱，便于直接观察波动集中度与尾部差异。</p>
<nav class="topnav"><a href="../index.html">← 返回首页</a><a href="../methodology.html">方法与数据说明</a></nav>
<div class="status"><span>最新交易日 <strong id="latest-date"></strong></span><span>区间 <strong>左闭右开</strong></span><span>纵轴 <strong>交易日占比</strong></span><span>更新 <strong>交易日 17:30</strong></span></div>
<section class="grid" id="chart-grid" aria-label="指数每日涨跌幅分布图"></section>
<div class="footer">中证系列指数行情来自中证指数有限公司历史行情接口；创业板指行情来自搜狐证券公开行情。统计从各指数正式发布日期起算，首个交易日使用行情源公布的当日涨跌幅。历史数据可能因指数公司回溯修订而变化。历史收益不代表未来表现，不构成投资建议。</div>
</main><div class="tooltip" id="tooltip" role="tooltip"></div>
<script>
const DATA={data_json};
const NS="http://www.w3.org/2000/svg";
const grid=document.getElementById("chart-grid");
const tooltip=document.getElementById("tooltip");
document.getElementById("latest-date").textContent=DATA.latestDate;
const allShares=DATA.series.flatMap(series=>series.bins.map(bin=>bin.share));
const yMax=Math.ceil(Math.max(...allShares)/5)*5;
const [xMin,xMax]=DATA.domain;
const W=360,H=230,M={{top:12,right:10,bottom:35,left:43}},PW=W-M.left-M.right,PH=H-M.top-M.bottom;
const sx=value=>M.left+(value-xMin)/(xMax-xMin)*PW;
const sy=value=>M.top+PH-value/yMax*PH;
const node=(name,attrs={{}})=>{{const el=document.createElementNS(NS,name);for(const [key,value] of Object.entries(attrs))el.setAttribute(key,value);return el}};
const label=(svg,text,x,y,anchor="middle")=>{{const el=node("text",{{x,y,"text-anchor":anchor}});el.textContent=text;svg.appendChild(el)}};
function signed(value){{return `${{value>0?"+":""}}${{value}}%`}}
function draw(series,index){{
  const article=document.createElement("article");article.className="panel";
  article.innerHTML=`<div class="panel-head"><h2>${{series.name}}</h2><span class="code">${{series.code}}</span></div><div class="meta">${{series.launchDate}} 起 · ${{series.count.toLocaleString("zh-CN")}} 日 · 日波动率 ${{series.stdev.toFixed(2)}}%</div><div class="chart"></div>`;
  const svg=node("svg",{{viewBox:`0 0 ${{W}} ${{H}}`,role:"img","aria-label":`${{series.name}}每日涨跌幅直方图`}});
  svg.appendChild(node("rect",{{x:M.left,y:M.top,width:PW,height:PH,class:"frame"}}));
  for(const value of [0,yMax/2,yMax]){{svg.appendChild(node("line",{{x1:M.left,x2:W-M.right,y1:sy(value),y2:sy(value),class:"gridline"}}));label(svg,`${{value.toFixed(0)}}%`,M.left-6,sy(value)+3,"end")}}
  const tickStep=xMax-xMin>24?5:4;
  const firstTick=Math.ceil(xMin/tickStep)*tickStep;
  for(let value=firstTick;value<=xMax;value+=tickStep){{label(svg,value>0?`+${{value}}`:String(value),sx(value),H-17)}}
  svg.appendChild(node("line",{{x1:sx(0),x2:sx(0),y1:M.top,y2:M.top+PH,class:"zero"}}));
  for(const bin of series.bins){{
    const rect=node("rect",{{x:sx(bin.x0)+1,y:sy(bin.share),width:Math.max(1,sx(bin.x1)-sx(bin.x0)-2),height:sy(0)-sy(bin.share),class:"bar",tabindex:"0","aria-label":`${{signed(bin.x0)}}至${{signed(bin.x1)}}：${{bin.count}}日，占${{bin.share.toFixed(1)}}%`}});
    const show=event=>{{tooltip.style.display="block";tooltip.innerHTML=`<strong>${{series.name}}</strong><br>${{signed(bin.x0)}} ～ ${{signed(bin.x1)}}<br>${{bin.count}} 个交易日 · ${{bin.share.toFixed(1)}}%`;tooltip.style.left=`${{Math.min(innerWidth-170,event.clientX+12)}}px`;tooltip.style.top=`${{Math.max(8,event.clientY-60)}}px`}};
    rect.addEventListener("pointerenter",show);rect.addEventListener("pointermove",show);rect.addEventListener("pointerleave",()=>tooltip.style.display="none");rect.addEventListener("focus",event=>show({{clientX:event.target.getBoundingClientRect().left,clientY:event.target.getBoundingClientRect().top}}));rect.addEventListener("blur",()=>tooltip.style.display="none");svg.appendChild(rect);
  }}
  label(svg,"单日涨跌幅（%）",M.left+PW/2,H-3);
  article.querySelector(".chart").appendChild(svg);grid.appendChild(article);
}}
DATA.series.forEach(draw);
</script></body></html>"""


def inject_home_link(site_dir: Path) -> None:
    index_path = site_dir / "index.html"
    content = index_path.read_text(encoding="utf-8")
    href = "daily-distributions/index.html"
    if href in content:
        return
    marker = '<nav class="topnav">'
    if marker not in content:
        raise RuntimeError("首页缺少 topnav，无法注入每日分布入口")
    content = content.replace(
        marker,
        marker + f'<a href="{href}">每日涨跌幅分布</a>',
        1,
    )
    index_path.write_text(content, encoding="utf-8")


def build_distribution_site(
    site_dir: Path,
    end_date: date,
    *,
    fetcher: Callable[[date], list[IndexReturns]] = fetch_all,
) -> Path:
    datasets = fetcher(end_date)
    payload = build_payload(datasets)
    output_dir = site_dir / "daily-distributions"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "index.html"
    output_path.write_text(render_page(payload), encoding="utf-8")
    inject_home_link(site_dir)
    print(f"daily distributions: {output_path.resolve()}")
    return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成指数每日涨跌幅分布子页面")
    parser.add_argument("--site-dir", type=Path, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, default=date.today())
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    build_distribution_site(args.site_dir, args.end_date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
