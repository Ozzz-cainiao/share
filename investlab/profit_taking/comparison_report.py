from __future__ import annotations

import html
from pathlib import Path

from investlab.profit_taking.comparison_sections import (
    calculate_simple_xirr,
    money,
    percent,
    render_baseline_sections,
    render_drawdown_sections,
    render_partial_sections,
    render_recycled_sections,
    render_retained_sections,
    signed_money,
)
from investlab.profit_taking.recycled_backtest import RecycledBacktestResult
from investlab.profit_taking.simple_backtest import SimpleBacktestResult
from investlab.profit_taking.simple_report_styles import CSS


def render_comparison_report(
    baseline: SimpleBacktestResult,
    retained: SimpleBacktestResult,
    recycled: RecycledBacktestResult,
    partial: SimpleBacktestResult,
    drawdown: SimpleBacktestResult,
    *,
    provider: str,
    checksum: str,
) -> str:
    retained_summary = retained.summary
    contribution = _plain_number(retained.config.monthly_contribution)
    target = f"{retained.config.target_return * 100:g}"
    baseline_xirr = calculate_simple_xirr(baseline)
    retained_xirr = calculate_simple_xirr(retained)
    partial_xirr = calculate_simple_xirr(partial)
    drawdown_xirr = calculate_simple_xirr(drawdown)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="沪深300全收益指数持续定投基准与四种止盈方案对比">
<title>沪深300定投止盈策略研究</title>
<style>{CSS}</style>
</head>
<body>
<main class="shell">
  <header class="hero">
    <div>
      <p class="overline">H00300 TOTAL RETURN · PROFIT-TAKING STUDY</p>
      <h1>一个基准，<br>四种止盈处理方式</h1>
      <p class="lead">{retained_summary.start_date.isoformat()} 至 {retained_summary.end_date.isoformat()}。每月定投 {contribution} 元；以持续持有、不止盈为基准，<span class="nowrap">对比</span>全部止盈、资金池复投、半仓止盈和<span class="nowrap">回撤止盈</span>。</p>
    </div>
    <dl class="headline-result">
      <div><dt>共同累计定投</dt><dd>{money(retained_summary.total_invested)}</dd></div>
      <div><dt>比较组合</dt><dd>5 种</dd></div>
    </dl>
  </header>

  <section aria-labelledby="comparison-title">
    <div class="section-heading">
      <p class="overline">COMPARISON</p>
      <h2 id="comparison-title">结果对比</h2>
    </div>
    {_render_comparison_table(baseline, retained, recycled, partial, drawdown, baseline_xirr, retained_xirr, partial_xirr, drawdown_xirr)}
  </section>

  <article class="scenario" aria-labelledby="scenario-baseline-title">
    <header class="scenario-header">
      <div><span class="scenario-number">基准 00</span></div>
      <div>
        <h2 id="scenario-baseline-title">基准：持续定投，从不止盈</h2>
        <p>每月投入全部留在指数中，不卖出、不建立止盈资金池，作为所有止盈方案的参照。</p>
      </div>
    </header>
    {render_baseline_sections(baseline, baseline_xirr)}
  </article>

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

  <article class="scenario" aria-labelledby="scenario-drawdown-title">
    <header class="scenario-header">
      <div><span class="scenario-number">方案 04</span></div>
      <div>
        <h2 id="scenario-drawdown-title">方案四：收益达到 {target}% 后，<span class="nowrap">回撤 10%</span> 全部止盈</h2>
        <p>本轮收益达到 {target}% 时启动跟踪；此后峰值随指数<span class="nowrap">创新高</span>而上移，从峰值回撤 10% 时全部卖出，<span class="nowrap">月度定投</span>持续进行。</p>
      </div>
    </header>
    {render_drawdown_sections(drawdown, drawdown_xirr)}
  </article>

  <section class="method" aria-labelledby="shared-method-title">
    <div>
      <p class="overline">SHARED METHOD</p>
      <h2 id="shared-method-title">共同口径</h2>
    </div>
    <div class="method-copy">
      <p>五组回测使用完全相同的 H00300 全收益指数、定投日期和月度金额。基准从不止盈；<span class="nowrap">方案一和方案二</span>达到 {target}% 时卖出全部持仓；方案三卖出 50%；方案四在达到 {target}% 后跟踪价格峰值，回撤 10% 时卖出全部持仓。</p>
      <p>累计收益率均使用“总盈利 ÷ 外部新增投入”。XIRR 将真实日期上的外部投入记为负现金流，将期末全部资产记为正现金流。</p>
      <p>“相对基准盈利差额”只比较期末盈利金额。方案二的外部投入较少，判断效率时应同时参考累计收益率和 XIRR。</p>
      <p class="source">数据：{html.escape(provider)} · SHA-256 {html.escape(checksum)} · 原始 H00300 <span class="nowrap">全收益指数</span>。</p>
    </div>
  </section>

  <footer>历史回测不代表未来表现。本页面仅用于投资方法研究，不构成投资建议。</footer>
</main>
</body>
</html>"""


def write_comparison_report(
    output_dir: Path,
    baseline: SimpleBacktestResult,
    retained: SimpleBacktestResult,
    recycled: RecycledBacktestResult,
    partial: SimpleBacktestResult,
    drawdown: SimpleBacktestResult,
    *,
    provider: str,
    checksum: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "index.html"
    report_path.write_text(
        render_comparison_report(
            baseline,
            retained,
            recycled,
            partial,
            drawdown,
            provider=provider,
            checksum=checksum,
        ),
        encoding="utf-8",
    )
    return report_path


def _render_comparison_table(
    baseline: SimpleBacktestResult,
    retained: SimpleBacktestResult,
    recycled: RecycledBacktestResult,
    partial: SimpleBacktestResult,
    drawdown: SimpleBacktestResult,
    baseline_xirr: float,
    retained_xirr: float,
    partial_xirr: float,
    drawdown_xirr: float,
) -> str:
    reference = baseline.summary
    first = retained.summary
    second = recycled.summary
    third = partial.summary
    fourth = drawdown.summary
    rows = (
        (
            "外部新增投入",
            money(reference.total_invested),
            money(first.total_invested),
            money(second.external_invested),
            money(third.total_invested),
            money(fourth.total_invested),
        ),
        (
            "期末总资产",
            money(reference.total_assets),
            money(first.total_assets),
            money(second.total_assets),
            money(third.total_assets),
            money(fourth.total_assets),
        ),
        (
            "总盈利",
            signed_money(reference.total_profit),
            signed_money(first.total_profit),
            signed_money(second.total_profit),
            signed_money(third.total_profit),
            signed_money(fourth.total_profit),
        ),
        (
            "相对基准盈利差额",
            "—",
            signed_money(first.total_profit - reference.total_profit),
            signed_money(second.total_profit - reference.total_profit),
            signed_money(third.total_profit - reference.total_profit),
            signed_money(fourth.total_profit - reference.total_profit),
        ),
        (
            "累计收益率",
            percent(reference.total_return),
            percent(first.total_return),
            percent(second.cumulative_return),
            percent(third.total_return),
            percent(fourth.total_return),
        ),
        (
            "XIRR 年化收益率",
            percent(baseline_xirr),
            percent(retained_xirr),
            percent(second.annualized_return),
            percent(partial_xirr),
            percent(drawdown_xirr),
        ),
        (
            "止盈次数",
            f"{reference.profit_take_count} 次",
            f"{first.profit_take_count} 次",
            f"{second.profit_take_count} 次",
            f"{third.profit_take_count} 次",
            f"{fourth.profit_take_count} 次",
        ),
    )
    body = "".join(
        f'<tr><th scope="row">{label}</th><td>{reference_value}</td>'
        f"<td>{first_value}</td><td>{second_value}</td><td>{third_value}</td>"
        f"<td>{fourth_value}</td></tr>"
        for label, reference_value, first_value, second_value, third_value, fourth_value in rows
    )
    return f"""<div class="table-wrap" tabindex="0">
<table class="comparison-table">
<caption>相同市场投入计划下的资金结果</caption>
<thead><tr><th scope="col">指标</th><th scope="col">持续定投不止盈</th><th scope="col">止盈所得不投入</th><th scope="col">止盈所得全部投入</th><th scope="col">每次止盈 50%</th><th scope="col">20% 激活 / 回撤 10%</th></tr></thead>
<tbody>{body}</tbody>
</table>
</div>"""


def _plain_number(value: float) -> str:
    return f"{value:,.2f}".rstrip("0").rstrip(".")
