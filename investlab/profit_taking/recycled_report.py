from __future__ import annotations

import csv
import html
import json
from dataclasses import asdict
from datetime import date
from io import StringIO
from pathlib import Path

from investlab.profit_taking.recycled_backtest import RecycledBacktestResult
from investlab.profit_taking.simple_report_styles import CSS


def render_recycled_report(
    result: RecycledBacktestResult,
    *,
    provider: str,
    checksum: str,
) -> str:
    summary = result.summary
    contribution_text = f"{result.config.monthly_contribution:,.2f}".rstrip("0").rstrip(
        "."
    )
    target_text = f"{result.config.target_return * 100:g}"
    ledger = _render_ledger(result)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="沪深300全收益指数止盈所得循环投入定投资金池回测结果">
<title>沪深300止盈资金池循环定投回测</title>
<style>{CSS}</style>
</head>
<body>
<main class="shell">
  <header class="hero">
    <div>
      <p class="overline">H00300 · RECYCLED CONTRIBUTION POOL</p>
      <h1>止盈所得循环支付定投，<br>外部投入降至 {_money(summary.external_invested)}</h1>
      <p class="lead">{summary.start_date.isoformat()} 至 {summary.end_date.isoformat()}。每月向指数投入 {contribution_text} 元，达到 {target_text}% 后全部止盈，<span class="nowrap">止盈所得优先支付后续定投</span>，不足部分才新增外部资金。</p>
    </div>
    <dl class="headline-result">
      <div><dt>期末总资产</dt><dd>{_money(summary.total_assets)}</dd></div>
      <div class="profit"><dt>总盈利</dt><dd>{_signed_money(summary.total_profit)}</dd></div>
    </dl>
  </header>

  <section aria-labelledby="summary-title">
    <div class="section-heading">
      <p class="overline">CAPITAL</p>
      <h2 id="summary-title">资金结果</h2>
    </div>
    <dl class="result-grid">
      {_metric("外部新增投入", _money(summary.external_invested), "真正新增的个人资金")}
      {_metric("累计投向市场", _money(summary.scheduled_contributions), f"{summary.contribution_count} 次月度定投")}
      {_metric("资金池循环投入", _money(summary.recycled_contributions), "由历史止盈所得支付")}
      {_metric("期末定投资金池", _money(summary.funding_pool), "现金收益率按 0% 计算")}
      {_metric("累计收益率", _percent(summary.cumulative_return), "总盈利 ÷ 外部新增投入")}
      {_metric("XIRR 年化收益率", _percent(summary.annualized_return), "按真实日期计算资金加权收益率")}
      {_metric("当前持仓市值", _money(summary.current_holding_value), "尚未触发止盈的本轮持仓")}
      {_metric("全部止盈次数", f"{summary.profit_take_count} 次", "每次出售全部持仓")}
    </dl>
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
      <p>每月第一个交易日投入 {contribution_text} 元。定投资金池有余额时优先扣款，不足部分记为外部新增投入。达到或超过 {target_text}% 时，按当日收盘全部止盈并将全部止盈所得放入定投资金池。</p>
      <p><strong>累计收益率 = 总盈利 ÷ 外部新增投入</strong>。XIRR 将每笔外部新增投入记为负现金流，将期末资金池与持仓总值记为正现金流，按真实日期求资金加权年化收益率。</p>
      <p>资金池收益率为 0%，不考虑手续费、税费和滑点。累计投向市场包含内部循环资金，不能重复计作外部投入。</p>
      <p class="source">数据：{html.escape(provider)} · SHA-256 {html.escape(checksum)} · 原始 H00300 全收益指数。</p>
    </div>
  </section>

  <footer>历史回测不代表未来表现。本页面仅用于投资方法研究，不构成投资建议。</footer>
</main>
</body>
</html>"""


def write_recycled_outputs(
    output_dir: Path,
    result: RecycledBacktestResult,
    *,
    provider: str,
    checksum: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "index.html"
    report_path.write_text(
        render_recycled_report(result, provider=provider, checksum=checksum),
        encoding="utf-8",
    )
    (output_dir / "summary.json").write_text(
        json.dumps(asdict(result.summary), ensure_ascii=False, indent=2, default=str)
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
    _write_csv(
        output_dir / "external_cash_flows.csv",
        tuple(asdict(row) for row in result.external_cash_flows),
    )
    return report_path


def _write_csv(
    path: Path,
    rows: tuple[dict[str, str | int | float | date], ...],
) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8-sig")


def _render_ledger(result: RecycledBacktestResult) -> str:
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


def _metric(label: str, value: str, note: str) -> str:
    return (
        f"<div><dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>"
        f"<p>{html.escape(note)}</p></div>"
    )


def _money(value: float) -> str:
    return f"¥{value:,.2f}"


def _signed_money(value: float) -> str:
    sign = "+" if value >= 0 else "−"
    return f"{sign}¥{abs(value):,.2f}"


def _percent(value: float) -> str:
    return f"{value * 100:+.2f}%"
