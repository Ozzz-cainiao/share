from __future__ import annotations

import html
from pathlib import Path

from investlab.profit_taking.comparison_sections import (
    calculate_simple_xirr,
    money,
    percent,
    render_partial_sections,
    render_recycled_sections,
    render_retained_sections,
    signed_money,
)
from investlab.profit_taking.recycled_backtest import RecycledBacktestResult
from investlab.profit_taking.simple_backtest import SimpleBacktestResult
from investlab.profit_taking.simple_report_styles import CSS


def render_comparison_report(
    retained: SimpleBacktestResult,
    recycled: RecycledBacktestResult,
    partial: SimpleBacktestResult,
    *,
    provider: str,
    checksum: str,
) -> str:
    retained_summary = retained.summary
    contribution = _plain_number(retained.config.monthly_contribution)
    target = f"{retained.config.target_return * 100:g}"
    retained_xirr = calculate_simple_xirr(retained)
    partial_xirr = calculate_simple_xirr(partial)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="沪深300全收益指数每月定投的全部止盈与半仓止盈对比">
<title>沪深300定投止盈策略研究</title>
<style>{CSS}</style>
</head>
<body>
<main class="shell">
  <header class="hero">
    <div>
      <p class="overline">H00300 TOTAL RETURN · PROFIT-TAKING STUDY</p>
      <h1>同一定投与止盈阈值，<br>三种止盈处理方式</h1>
      <p class="lead">{retained_summary.start_date.isoformat()} 至 {retained_summary.end_date.isoformat()}。每月定投 {contribution} 元，累计收益达到 {target}% 后，分别测试全部止盈、资金池复投和半仓止盈。</p>
    </div>
    <dl class="headline-result">
      <div><dt>共同累计定投</dt><dd>{money(retained_summary.total_invested)}</dd></div>
      <div><dt>回测方案</dt><dd>3 种</dd></div>
    </dl>
  </header>

  <section aria-labelledby="comparison-title">
    <div class="section-heading">
      <p class="overline">COMPARISON</p>
      <h2 id="comparison-title">结果对比</h2>
    </div>
    {_render_comparison_table(retained, recycled, partial, retained_xirr, partial_xirr)}
  </section>

  <article class="scenario" aria-labelledby="scenario-retained-title">
    <header class="scenario-header">
      <div><span class="scenario-number">方案 01</span></div>
      <div>
        <h2 id="scenario-retained-title">方案一：止盈所得不再投入</h2>
        <p>每月定投始终由新增外部资金支付；全部止盈所得留在零收益资金池。</p>
      </div>
    </header>
    {render_retained_sections(retained, retained_xirr)}
  </article>

  <article class="scenario" aria-labelledby="scenario-recycled-title">
    <header class="scenario-header">
      <div><span class="scenario-number">方案 02</span></div>
      <div>
        <h2 id="scenario-recycled-title">方案二：止盈所得全部投入定投资金池</h2>
        <p>全部止盈所得优先支付后续月度定投，不足部分才新增外部资金。</p>
      </div>
    </header>
    {render_recycled_sections(recycled)}
  </article>

  <article class="scenario" aria-labelledby="scenario-partial-title">
    <header class="scenario-header">
      <div><span class="scenario-number">方案 03</span></div>
      <div>
        <h2 id="scenario-partial-title">方案三：每次止盈 50% 持仓</h2>
        <p>触发时卖出一半持仓并留在零收益资金池；剩余持仓按当日市值重置成本基准，再上涨 {target}% 后才<span class="nowrap">再次触发</span>。</p>
      </div>
    </header>
    {render_partial_sections(partial, partial_xirr)}
  </article>

  <section class="method" aria-labelledby="shared-method-title">
    <div>
      <p class="overline">SHARED METHOD</p>
      <h2 id="shared-method-title">共同口径</h2>
    </div>
    <div class="method-copy">
      <p>三种方案使用完全相同的 H00300 全收益指数、定投日期、月度金额和 {target}% 止盈阈值。<span class="nowrap">方案一和方案二</span>每次卖出全部持仓；方案三每次卖出 50% 持仓并重置剩余仓位的成本基准。</p>
      <p>累计收益率均使用“总盈利 ÷ 外部新增投入”。XIRR 将真实日期上的外部投入记为负现金流，将期末全部资产记为正现金流。</p>
      <p class="source">数据：{html.escape(provider)} · SHA-256 {html.escape(checksum)} · 原始 H00300 <span class="nowrap">全收益指数</span>。</p>
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
    partial: SimpleBacktestResult,
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
            partial,
            provider=provider,
            checksum=checksum,
        ),
        encoding="utf-8",
    )
    return report_path


def _render_comparison_table(
    retained: SimpleBacktestResult,
    recycled: RecycledBacktestResult,
    partial: SimpleBacktestResult,
    retained_xirr: float,
    partial_xirr: float,
) -> str:
    first = retained.summary
    second = recycled.summary
    third = partial.summary
    rows = (
        (
            "外部新增投入",
            money(first.total_invested),
            money(second.external_invested),
            money(third.total_invested),
        ),
        (
            "期末总资产",
            money(first.total_assets),
            money(second.total_assets),
            money(third.total_assets),
        ),
        (
            "总盈利",
            signed_money(first.total_profit),
            signed_money(second.total_profit),
            signed_money(third.total_profit),
        ),
        (
            "累计收益率",
            percent(first.total_return),
            percent(second.cumulative_return),
            percent(third.total_return),
        ),
        (
            "XIRR 年化收益率",
            percent(retained_xirr),
            percent(second.annualized_return),
            percent(partial_xirr),
        ),
        (
            "止盈次数",
            f"{first.profit_take_count} 次",
            f"{second.profit_take_count} 次",
            f"{third.profit_take_count} 次",
        ),
    )
    body = "".join(
        f'<tr><th scope="row">{label}</th><td>{first_value}</td>'
        f"<td>{second_value}</td><td>{third_value}</td></tr>"
        for label, first_value, second_value, third_value in rows
    )
    return f"""<div class="table-wrap" tabindex="0">
<table class="comparison-table">
<caption>相同市场投入计划下的资金结果</caption>
<thead><tr><th scope="col">指标</th><th scope="col">止盈所得不投入</th><th scope="col">止盈所得全部投入</th><th scope="col">每次止盈 50%</th></tr></thead>
<tbody>{body}</tbody>
</table>
</div>"""


def _plain_number(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")
