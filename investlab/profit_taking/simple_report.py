from __future__ import annotations

import csv
import html
import json
from dataclasses import asdict
from datetime import date
from io import StringIO
from pathlib import Path

from investlab.profit_taking.simple_backtest import SimpleBacktestResult
from investlab.profit_taking.simple_report_styles import CSS


def render_simple_report(
    result: SimpleBacktestResult,
    *,
    provider: str,
    checksum: str,
) -> str:
    summary = result.summary
    contribution_text = f"{result.config.monthly_contribution:,.2f}".rstrip("0").rstrip(
        "."
    )
    target_text = f"{result.config.target_return * 100:g}"
    chart = render_simple_chart(result)
    ledger = render_simple_ledger(result)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="沪深300全收益指数2019年至今每月定投{contribution_text}元、累计收益{target_text}%全部止盈回测结果">
<title>沪深300每月定投{target_text}%止盈回测</title>
<style>{CSS}</style>
</head>
<body>
<main class="shell">
  <header class="hero">
    <div>
      <p class="overline">H00300 TOTAL RETURN · SIMPLE BACKTEST</p>
      <h1>每月定投 {contribution_text} 元，<br>累计收益 {target_text}% 全部止盈</h1>
      <p class="lead">{summary.start_date.isoformat()} 至 {summary.end_date.isoformat()}。定投持续进行，止盈所得进入零收益资金池，不再投入市场。</p>
    </div>
    <dl class="headline-result">
      <div><dt>期末总资产</dt><dd>{_money(summary.total_assets)}</dd></div>
      <div class="profit"><dt>总盈利</dt><dd>{_signed_money(summary.total_profit)}</dd></div>
    </dl>
  </header>

  <section aria-labelledby="summary-title">
    <div class="section-heading">
      <p class="overline">RESULT</p>
      <h2 id="summary-title">核心结果</h2>
    </div>
    <dl class="result-grid">
      {_metric("总投入", _money(summary.total_invested), f"{summary.contribution_count} 次月度投入")}
      {_metric("止盈资金池", _money(summary.reserve_pool), "止盈本金与利润均保留")}
      {_metric("当前持仓市值", _money(summary.current_holding_value), "尚未触发止盈的本轮持仓")}
      {_metric("总收益率", _percent(summary.total_return), "总盈利 ÷ 总投入")}
      {_metric("止盈次数", f"{summary.profit_take_count} 次", "每次均为全部止盈")}
      {_metric("交易日样本", f"{summary.trading_days:,} 日", f"截至 {summary.end_date.isoformat()}")}
    </dl>
  </section>

  <section class="figure-section" aria-labelledby="trajectory-title">
    <div class="section-heading">
      <p class="overline">TRAJECTORY</p>
      <h2 id="trajectory-title">资产轨迹</h2>
    </div>
    {chart}
  </section>

  <section aria-labelledby="ledger-title">
    <div class="section-heading">
      <p class="overline">LEDGER</p>
      <h2 id="ledger-title">止盈明细</h2>
    </div>
    {ledger}
  </section>

  <section class="method" aria-labelledby="method-title">
    <div>
      <p class="overline">METHOD</p>
      <h2 id="method-title">计算口径</h2>
    </div>
    <div class="method-copy">
      <p>每月第一个交易日按当日收盘点位投入 {contribution_text} 元。每日收盘先检查已有持仓；本轮累计收益率达到或超过 {target_text}% 时，以当日收盘点位全部止盈。若止盈日也是月度定投日，先止盈旧持仓，再投入新的 {contribution_text} 元。</p>
      <p><strong>本轮累计收益率 = 当前持仓市值 ÷ 本轮累计投入 − 1</strong>。该指标不是年化收益率。止盈资金池不计利息，回测不考虑手续费、税费和滑点。</p>
      <p class="source">数据：{html.escape(provider)} · SHA-256 {html.escape(checksum)} · 使用原始 H00300 全收益指数，不使用年度 1.026 修正。</p>
    </div>
  </section>

  <footer>历史回测不代表未来表现。本页面仅用于投资方法研究，不构成投资建议。</footer>
</main>
</body>
</html>"""


def write_simple_outputs(
    output_dir: Path,
    result: SimpleBacktestResult,
    *,
    provider: str,
    checksum: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "index.html"
    report_path.write_text(
        render_simple_report(result, provider=provider, checksum=checksum),
        encoding="utf-8",
    )
    (output_dir / "summary.json").write_text(
        json.dumps(
            asdict(result.summary),
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        + "\n",
        encoding="utf-8",
    )
    _write_csv(
        output_dir / "profit_takes.csv",
        tuple(asdict(row) for row in result.profit_takes),
    )
    _write_csv(
        output_dir / "daily.csv",
        tuple(asdict(row) for row in result.daily_rows),
    )
    return report_path


def _write_csv(
    path: Path, rows: tuple[dict[str, str | int | float | date], ...]
) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8-sig")


def _metric(label: str, value: str, note: str) -> str:
    return (
        f"<div><dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>"
        f"<p>{html.escape(note)}</p></div>"
    )


def render_simple_chart(result: SimpleBacktestResult) -> str:
    rows = result.daily_rows
    maximum = max(row.total_assets for row in rows)
    width = 1_000.0
    height = 320.0
    left = 24.0
    top = 20.0
    plot_width = width - left * 2
    plot_height = height - top * 2
    denominator = max(len(rows) - 1, 1)

    def points(values: tuple[float, ...]) -> str:
        return " ".join(
            f"{left + plot_width * index / denominator:.2f},"
            f"{top + plot_height * (1 - value / maximum):.2f}"
            for index, value in enumerate(values)
        )

    assets = points(tuple(row.total_assets for row in rows))
    invested = points(
        tuple(
            result.config.monthly_contribution
            * sum(item.contribution > 0 for item in rows[: index + 1])
            for index in range(len(rows))
        )
    )
    reserve = points(tuple(row.reserve_pool for row in rows))
    return f"""<figure class="chart">
<svg viewBox="0 0 1000 320" role="img" aria-labelledby="chart-title chart-desc">
  <title id="chart-title">沪深300定投止盈资产轨迹</title>
  <desc id="chart-desc">展示总资产、累计投入与止盈资金池从回测开始到结束的变化。</desc>
  <line class="axis" x1="24" y1="300" x2="976" y2="300"/>
  <polyline class="line invested" points="{invested}"/>
  <polyline class="line reserve" points="{reserve}"/>
  <polyline class="line assets" points="{assets}"/>
</svg>
<figcaption><span class="key assets-key">总资产</span><span class="key invested-key">累计投入</span><span class="key reserve-key">止盈资金池</span></figcaption>
</figure>"""


def render_simple_ledger(result: SimpleBacktestResult) -> str:
    if not result.profit_takes:
        return '<p class="empty">回测区间内没有触发全部止盈。</p>'
    rows = "".join(
        "<tr>"
        f"<td>{event.sequence}</td>"
        f"<td>{event.date.isoformat()}</td>"
        f"<td>{_money(event.cycle_invested)}</td>"
        f"<td>{_money(event.proceeds)}</td>"
        f"<td>{_signed_money(event.cycle_profit)}</td>"
        f"<td>{_percent(event.cycle_return)}</td>"
        "</tr>"
        for event in result.profit_takes
    )
    return f"""<div class="table-wrap" tabindex="0">
<table>
<caption>全部止盈记录</caption>
<thead><tr><th scope="col">次数</th><th scope="col">止盈日期</th><th scope="col">本轮投入</th><th scope="col">止盈金额</th><th scope="col">本轮盈利</th><th scope="col">本轮累计收益率</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""


def _money(value: float) -> str:
    return f"¥{value:,.2f}"


def _signed_money(value: float) -> str:
    sign = "+" if value >= 0 else "−"
    return f"{sign}¥{abs(value):,.2f}"


def _percent(value: float) -> str:
    return f"{value * 100:+.2f}%"
