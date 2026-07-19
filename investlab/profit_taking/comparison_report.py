from __future__ import annotations

import html
from pathlib import Path

from investlab.profit_taking.recycled_backtest import (
    ExternalCashFlow,
    RecycledBacktestResult,
    calculate_xirr,
)
from investlab.profit_taking.recycled_report import render_recycled_ledger
from investlab.profit_taking.simple_backtest import SimpleBacktestResult
from investlab.profit_taking.simple_report import (
    render_simple_chart,
    render_simple_ledger,
)
from investlab.profit_taking.simple_report_styles import CSS


def render_comparison_report(
    retained: SimpleBacktestResult,
    recycled: RecycledBacktestResult,
    *,
    provider: str,
    checksum: str,
) -> str:
    retained_summary = retained.summary
    contribution = _plain_number(retained.config.monthly_contribution)
    target = f"{retained.config.target_return * 100:g}"
    retained_xirr = _calculate_retained_xirr(retained)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="沪深300全收益指数每月定投与全部止盈的资金去向对比">
<title>沪深300定投止盈策略研究</title>
<style>{CSS}</style>
</head>
<body>
<main class="shell">
  <header class="hero">
    <div>
      <p class="overline">H00300 TOTAL RETURN · PROFIT-TAKING STUDY</p>
      <h1>同一止盈策略，<br>两种止盈资金处理方式</h1>
      <p class="lead">{retained_summary.start_date.isoformat()} 至 {retained_summary.end_date.isoformat()}。每月定投 {contribution} 元，累计收益达到 {target}% 后全部止盈；仅改变止盈所得是否支付后续定投。</p>
    </div>
    <dl class="headline-result">
      <div><dt>累计投向市场</dt><dd>{_money(retained_summary.total_invested)}</dd></div>
      <div class="profit"><dt>两种方案总盈利</dt><dd>{_signed_money(retained_summary.total_profit)}</dd></div>
    </dl>
  </header>

  <section aria-labelledby="comparison-title">
    <div class="section-heading">
      <p class="overline">COMPARISON</p>
      <h2 id="comparison-title">结果对比</h2>
    </div>
    {_render_comparison_table(retained, recycled, retained_xirr)}
  </section>

  <article class="scenario" aria-labelledby="scenario-retained-title">
    <header class="scenario-header">
      <div><span class="scenario-number">方案 01</span></div>
      <div>
        <h2 id="scenario-retained-title">方案一：止盈所得不再投入</h2>
        <p>每月定投始终由新增外部资金支付；全部止盈所得留在零收益资金池。</p>
      </div>
    </header>
    {_render_retained_sections(retained, retained_xirr)}
  </article>

  <article class="scenario" aria-labelledby="scenario-recycled-title">
    <header class="scenario-header">
      <div><span class="scenario-number">方案 02</span></div>
      <div>
        <h2 id="scenario-recycled-title">方案二：止盈所得全部投入定投资金池</h2>
        <p>全部止盈所得优先支付后续月度定投，不足部分才新增外部资金。</p>
      </div>
    </header>
    {_render_recycled_sections(recycled)}
  </article>

  <section class="method" aria-labelledby="shared-method-title">
    <div>
      <p class="overline">SHARED METHOD</p>
      <h2 id="shared-method-title">共同口径</h2>
    </div>
    <div class="method-copy">
      <p>两种方案使用完全相同的 H00300 全收益指数、定投日期、月度金额和 {target}% 全部止盈信号。资金池收益率按 0% 计算，不考虑手续费、税费和滑点。</p>
      <p>累计收益率均使用“总盈利 ÷ 外部新增投入”。XIRR 将真实日期上的外部投入记为负现金流，将期末全部资产记为正现金流。</p>
      <p class="source">数据：{html.escape(provider)} · SHA-256 {html.escape(checksum)} · 原始 H00300 全收益指数。</p>
    </div>
  </section>

  <footer>历史回测不代表未来表现。本页面仅用于投资方法研究，不构成投资建议。</footer>
</main>
</body>
</html>"""


def write_comparison_report(
    output_dir: Path,
    retained: SimpleBacktestResult,
    recycled: RecycledBacktestResult,
    *,
    provider: str,
    checksum: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "index.html"
    report_path.write_text(
        render_comparison_report(
            retained,
            recycled,
            provider=provider,
            checksum=checksum,
        ),
        encoding="utf-8",
    )
    return report_path


def _render_comparison_table(
    retained: SimpleBacktestResult,
    recycled: RecycledBacktestResult,
    retained_xirr: float,
) -> str:
    first = retained.summary
    second = recycled.summary
    rows = (
        (
            "外部新增投入",
            _money(first.total_invested),
            _money(second.external_invested),
        ),
        ("期末总资产", _money(first.total_assets), _money(second.total_assets)),
        (
            "总盈利",
            _signed_money(first.total_profit),
            _signed_money(second.total_profit),
        ),
        (
            "累计收益率",
            _percent(first.total_return),
            _percent(second.cumulative_return),
        ),
        (
            "XIRR 年化收益率",
            _percent(retained_xirr),
            _percent(second.annualized_return),
        ),
        (
            "全部止盈次数",
            f"{first.profit_take_count} 次",
            f"{second.profit_take_count} 次",
        ),
    )
    body = "".join(
        f'<tr><th scope="row">{label}</th><td>{first_value}</td>'
        f"<td>{second_value}</td></tr>"
        for label, first_value, second_value in rows
    )
    return f"""<div class="table-wrap" tabindex="0">
<table class="comparison-table">
<caption>相同市场投入计划下的资金结果</caption>
<thead><tr><th scope="col">指标</th><th scope="col">止盈所得不投入</th><th scope="col">止盈所得全部投入</th></tr></thead>
<tbody>{body}</tbody>
</table>
</div>"""


def _render_retained_sections(
    result: SimpleBacktestResult,
    annualized_return: float,
) -> str:
    summary = result.summary
    return f"""
<section aria-labelledby="retained-result-title">
  <div class="section-heading"><p class="overline">RESULT 01</p><h2 id="retained-result-title">资金结果</h2></div>
  <dl class="result-grid">
    {_metric("外部新增投入", _money(summary.total_invested), f"{summary.contribution_count} 次月度投入")}
    {_metric("期末总资产", _money(summary.total_assets), "资金池与当前持仓合计")}
    {_metric("止盈资金池", _money(summary.reserve_pool), "止盈所得不再投入")}
    {_metric("当前持仓市值", _money(summary.current_holding_value), "尚未触发止盈的本轮持仓")}
    {_metric("累计收益率", _percent(summary.total_return), "总盈利 ÷ 外部新增投入")}
    {_metric("XIRR 年化收益率", _percent(annualized_return), "按真实日期计算")}
    {_metric("总盈利", _signed_money(summary.total_profit), "期末总资产减外部投入")}
    {_metric("全部止盈次数", f"{summary.profit_take_count} 次", "每次出售全部持仓")}
  </dl>
</section>
<section aria-labelledby="retained-chart-title">
  <div class="section-heading"><p class="overline">TRAJECTORY 01</p><h2 id="retained-chart-title">资产轨迹</h2></div>
  {render_simple_chart(result)}
</section>
<section aria-labelledby="retained-ledger-title">
  <div class="section-heading"><p class="overline">LEDGER 01</p><h2 id="retained-ledger-title">止盈明细</h2></div>
  {render_simple_ledger(result)}
</section>"""


def _render_recycled_sections(result: RecycledBacktestResult) -> str:
    summary = result.summary
    return f"""
<section aria-labelledby="recycled-result-title">
  <div class="section-heading"><p class="overline">RESULT 02</p><h2 id="recycled-result-title">资金结果</h2></div>
  <dl class="result-grid">
    {_metric("外部新增投入", _money(summary.external_invested), "真正新增的个人资金")}
    {_metric("累计投向市场", _money(summary.scheduled_contributions), f"{summary.contribution_count} 次月度定投")}
    {_metric("资金池循环投入", _money(summary.recycled_contributions), "由历史止盈所得支付")}
    {_metric("期末定投资金池", _money(summary.funding_pool), "现金收益率按 0% 计算")}
    {_metric("累计收益率", _percent(summary.cumulative_return), "总盈利 ÷ 外部新增投入")}
    {_metric("XIRR 年化收益率", _percent(summary.annualized_return), "按真实日期计算")}
    {_metric("当前持仓市值", _money(summary.current_holding_value), "尚未触发止盈的本轮持仓")}
    {_metric("全部止盈次数", f"{summary.profit_take_count} 次", "每次出售全部持仓")}
  </dl>
</section>
<section aria-labelledby="recycled-ledger-title">
  <div class="section-heading"><p class="overline">LEDGER 02</p><h2 id="recycled-ledger-title">止盈明细</h2></div>
  {render_recycled_ledger(result)}
</section>"""


def _calculate_retained_xirr(result: SimpleBacktestResult) -> float:
    flows = tuple(
        ExternalCashFlow(row.date, -row.contribution)
        for row in result.daily_rows
        if row.contribution > 0
    )
    terminal = ExternalCashFlow(result.summary.end_date, result.summary.total_assets)
    return calculate_xirr((*flows, terminal))


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


def _plain_number(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")
