from __future__ import annotations

import html

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


def render_retained_sections(
    result: SimpleBacktestResult,
    annualized_return: float,
) -> str:
    summary = result.summary
    return f"""
<section aria-labelledby="retained-result-title">
  <div class="section-heading"><p class="overline">RESULT 01</p><h2 id="retained-result-title">资金结果</h2></div>
  <dl class="result-grid">
    {metric("外部新增投入", money(summary.total_invested), f"{summary.contribution_count} 次月度投入")}
    {metric("期末总资产", money(summary.total_assets), "资金池与当前持仓合计")}
    {metric("止盈资金池", money(summary.reserve_pool), "止盈所得不再投入")}
    {metric("当前持仓市值", money(summary.current_holding_value), "尚未触发止盈的本轮持仓")}
    {metric("累计收益率", percent(summary.total_return), "总盈利 ÷ 外部新增投入")}
    {metric("XIRR 年化收益率", percent(annualized_return), "按真实日期计算")}
    {metric("总盈利", signed_money(summary.total_profit), "期末总资产减外部投入")}
    {metric("全部止盈次数", f"{summary.profit_take_count} 次", "每次出售全部持仓")}
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


def render_recycled_sections(result: RecycledBacktestResult) -> str:
    summary = result.summary
    return f"""
<section aria-labelledby="recycled-result-title">
  <div class="section-heading"><p class="overline">RESULT 02</p><h2 id="recycled-result-title">资金结果</h2></div>
  <dl class="result-grid">
    {metric("外部新增投入", money(summary.external_invested), "真正新增的个人资金")}
    {metric("累计投向市场", money(summary.scheduled_contributions), f"{summary.contribution_count} 次月度定投")}
    {metric("资金池循环投入", money(summary.recycled_contributions), "由历史止盈所得支付")}
    {metric("期末定投资金池", money(summary.funding_pool), "现金收益率按 0% 计算")}
    {metric("累计收益率", percent(summary.cumulative_return), "总盈利 ÷ 外部新增投入")}
    {metric("XIRR 年化收益率", percent(summary.annualized_return), "按真实日期计算")}
    {metric("当前持仓市值", money(summary.current_holding_value), "尚未触发止盈的本轮持仓")}
    {metric("全部止盈次数", f"{summary.profit_take_count} 次", "每次出售全部持仓")}
  </dl>
</section>
<section aria-labelledby="recycled-ledger-title">
  <div class="section-heading"><p class="overline">LEDGER 02</p><h2 id="recycled-ledger-title">止盈明细</h2></div>
  {render_recycled_ledger(result)}
</section>"""


def render_partial_sections(
    result: SimpleBacktestResult,
    annualized_return: float,
) -> str:
    summary = result.summary
    return f"""
<section aria-labelledby="partial-result-title">
  <div class="section-heading"><p class="overline">RESULT 03</p><h2 id="partial-result-title">资金结果</h2></div>
  <dl class="result-grid">
    {metric("外部新增投入", money(summary.total_invested), f"{summary.contribution_count} 次月度投入")}
    {metric("期末总资产", money(summary.total_assets), "资金池与当前持仓合计")}
    {metric("止盈资金池", money(summary.reserve_pool), "每次卖出半仓所得")}
    {metric("当前持仓市值", money(summary.current_holding_value), "持续保留的市场仓位")}
    {metric("累计收益率", percent(summary.total_return), "总盈利 ÷ 外部新增投入")}
    {metric("XIRR 年化收益率", percent(annualized_return), "按真实日期计算")}
    {metric("总盈利", signed_money(summary.total_profit), "期末总资产减外部投入")}
    {metric("半仓止盈次数", f"{summary.profit_take_count} 次", "每次出售 50% 持仓")}
  </dl>
</section>
<section aria-labelledby="partial-ledger-title">
  <div class="section-heading"><p class="overline">LEDGER 03</p><h2 id="partial-ledger-title">半仓止盈明细</h2></div>
  {_render_partial_ledger(result)}
</section>"""


def _render_partial_ledger(result: SimpleBacktestResult) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{event.sequence}</td>"
        f"<td>{event.date.isoformat()}</td>"
        f"<td>{money(event.cycle_invested)}</td>"
        f"<td>{money(event.proceeds)}</td>"
        f"<td>{signed_money(event.cycle_profit)}</td>"
        f"<td>{percent(event.cycle_return)}</td>"
        "</tr>"
        for event in result.profit_takes
    )
    return f"""<div class="table-wrap" tabindex="0">
<table>
<caption>50% 止盈记录</caption>
<thead><tr><th scope="col">次数</th><th scope="col">止盈日期</th><th scope="col">卖出部分成本基准</th><th scope="col">止盈金额</th><th scope="col">本次盈利</th><th scope="col">触发收益率</th></tr></thead>
<tbody>{rows}</tbody>
</table>
</div>"""


def calculate_simple_xirr(result: SimpleBacktestResult) -> float:
    flows = tuple(
        ExternalCashFlow(row.date, -row.contribution)
        for row in result.daily_rows
        if row.contribution > 0
    )
    terminal = ExternalCashFlow(result.summary.end_date, result.summary.total_assets)
    return calculate_xirr((*flows, terminal))


def metric(label: str, value: str, note: str) -> str:
    return (
        f"<div><dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>"
        f"<p>{html.escape(note)}</p></div>"
    )


def money(value: float) -> str:
    return f"¥{value:,.2f}"


def signed_money(value: float) -> str:
    sign = "+" if value >= 0 else "−"
    return f"{sign}¥{abs(value):,.2f}"


def percent(value: float) -> str:
    return f"{value * 100:+.2f}%"
