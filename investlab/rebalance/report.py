from __future__ import annotations

import html
from pathlib import Path

from investlab.rebalance.artifacts import MetricRow


def generate_research_report(
    results: list[MetricRow],
    output_dir: Path,
    drift_twr: float,
) -> None:
    ranked = _ranked(results)
    rows = "".join(_summary_row(row, drift_twr) for row in ranked)
    mobile_rows = "".join(_mobile_summary_row(row, drift_twr) for row in ranked)
    cards = "".join(_strategy_card(row, drift_twr) for row in ranked)
    (output_dir / "rebalance_comparison.html").write_text(
        _html(rows, mobile_rows, cards, drift_twr),
        encoding="utf-8",
    )


def _ranked(results: list[MetricRow]) -> list[MetricRow]:
    return sorted(
        results,
        key=lambda row: float(row.get("ann_return_twr") or -999.0),
        reverse=True,
    )


def _summary_row(row: MetricRow, drift_twr: float) -> str:
    twr = float(row.get("ann_return_twr") or 0.0)
    excess = twr - drift_twr
    css_class = "positive" if excess > 0 else "negative"
    sign = "+" if excess > 0 else ""
    name = html.escape(str(row.get("strategy_display") or row.get("strategy_name") or ""))
    return (
        f"<tr><td>{name}</td><td class='num'>{twr * 100:+.2f}%</td>"
        f"<td class='num {css_class}'>{sign}{excess * 100:.2f}%</td>"
        f"<td class='num'>{float(row.get('sharpe_twr') or 0.0):+.3f}</td>"
        f"<td class='num'>{float(row.get('max_drawdown_twr') or 0.0) * 100:.1f}%</td>"
        f"<td class='num'>{float(row.get('avg_turnover') or 0.0) * 100:.1f}%</td></tr>"
    )


def _mobile_summary_row(row: MetricRow, drift_twr: float) -> str:
    twr = float(row.get("ann_return_twr") or 0.0)
    excess = twr - drift_twr
    css_class = "positive" if excess > 0 else "negative"
    sign = "+" if excess > 0 else ""
    name = html.escape(str(row.get("strategy_display") or row.get("strategy_name") or ""))
    return (
        "<article class='mobile-result'>"
        f"<h3>{name}</h3>"
        f"<p><span>年化 TWR</span><strong>{twr * 100:+.2f}%</strong></p>"
        f"<p><span>超额收益</span><strong class='{css_class}'>{sign}{excess * 100:.2f}%</strong></p>"
        f"<p><span>Sharpe</span><strong>{float(row.get('sharpe_twr') or 0.0):+.3f}</strong></p>"
        f"<p><span>最大回撤</span><strong>{float(row.get('max_drawdown_twr') or 0.0) * 100:.1f}%</strong></p>"
        f"<p><span>换手率</span><strong>{float(row.get('avg_turnover') or 0.0) * 100:.1f}%</strong></p>"
        "</article>"
    )


def _strategy_card(row: MetricRow, drift_twr: float) -> str:
    name = str(row.get("strategy_name") or "")
    display, family, description, allocation = _strategy_text(name)
    twr = float(row.get("ann_return_twr") or 0.0)
    excess = twr - drift_twr
    css_class = "positive" if excess > 0 else "negative"
    sign = "+" if excess > 0 else ""
    return (
        "<div class='card'>"
        f"<div class='card-header'><span class='badge'>{family}</span>"
        f"<h3>{html.escape(display)}</h3></div>"
        "<div class='card-metrics'>"
        f"<div class='metric'><span>TWR</span><strong>{twr * 100:+.2f}%</strong></div>"
        f"<div class='metric'><span>超额</span><strong class='{css_class}'>{sign}{excess * 100:.2f}%</strong></div>"
        f"<div class='metric'><span>Sharpe</span><strong>{float(row.get('sharpe_twr') or 0.0):+.3f}</strong></div>"
        f"<div class='metric'><span>最大回撤</span><strong>{float(row.get('max_drawdown_twr') or 0.0) * 100:.1f}%</strong></div>"
        "</div>"
        f"<div class='card-body'><p><b>策略逻辑：</b>{description}</p>"
        f"<p><b>资产配置：</b>{allocation}</p></div></div>"
    )


def _strategy_text(name: str) -> tuple[str, str, str, str]:
    if name.startswith("blend_"):
        return (
            "固定混合",
            "blend",
            "将战略基准权重与动量排名权重按 λ 混合，并用免调带减少交易。",
            "战略纪律与趋势追随的凸组合。",
        )
    if name.startswith("fixed_rebal_"):
        return ("固定比例月度再平衡", "fixed_ratio", "每月恢复预设固定比例。", "固定目标比例。")
    if name.startswith("fixed_"):
        return ("固定比例买入持有", "fixed_ratio", "按预设固定比例买入后不主动调仓。", "权重随价格漂移。")
    mapping = {
        "drift": ("自然漂移", "drift", "初始等权买入后不再调仓。", "权重随市场自由漂移。"),
        "ew_monthly": ("等权月度再平衡", "calendar", "每月恢复三指数等权。", "33%/33%/33%。"),
        "ew_quarterly": ("等权季度再平衡", "calendar", "每季度恢复三指数等权。", "33%/33%/33%。"),
        "ew_annual": ("等权年度再平衡", "calendar", "每年恢复三指数等权。", "33%/33%/33%。"),
        "thresh_5": ("阈值再平衡 5%", "threshold", "偏离等权超过 5pp 时恢复等权。", "平时漂移，触发后等权。"),
        "thresh_10": ("阈值再平衡 10%", "threshold", "偏离等权超过 10pp 时恢复等权。", "高容忍漂移。"),
        "inv_vol": ("逆波动率加权", "inverse_vol", "按 63 日逆波动率分配，限制 10%-65%。", "低波动指数权重更高。"),
        "regime_adaptive": ("结构牛市自适应", "regime", "上升且分化时提高动量权重，否则降低动量权重。", "随状态切换 λ 和卖出带。"),
    }
    return mapping.get(name, (name, "strategy", "策略元数据未匹配。", "见 strategy_catalog.json。"))


def _html(rows: str, mobile_rows: str, cards: str, drift_twr: float) -> str:
    css = (
        ":root{--ink:#26304a;--muted:#68758b;--line:#dce2ed;--paper:#f5f7fb;--card:#fff;--brand:#405477}"
        "*{box-sizing:border-box}body{margin:0;overflow-x:hidden;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif}"
        ".shell{max-width:960px;margin:auto;padding:44px 28px 60px}h1{margin:8px 0 4px;font:600 34px Georgia,'Songti SC',serif}h2{margin:32px 0 12px;font-size:22px}"
        ".sub{color:var(--muted);font-size:15px;margin-bottom:24px;line-height:1.7}table{width:100%;border-collapse:collapse;background:var(--card);border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(35,45,75,.06);margin:18px 0}"
        "th,td{padding:12px 16px;text-align:left;border-bottom:1px solid var(--line);font-size:14px}th{background:#eef2f8;font-weight:600;font-size:13px}.num{text-align:right;font-variant-numeric:tabular-nums}.mobile-summary{display:none}"
        ".positive{color:#1a7a3a;font-weight:600}.negative{color:#b53636}.card{padding:22px;margin:14px 0;border:1px solid var(--line);border-radius:14px;background:var(--card);box-shadow:0 4px 18px rgba(35,45,75,.04)}"
        ".card-header{display:flex;align-items:center;gap:10px;margin-bottom:12px}.badge{display:inline-block;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600;background:#eef2f8;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}"
        ".card-header h3{margin:0;font-size:18px}.card-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0}.metric{padding:10px;background:#f8fafd;border-radius:8px;text-align:center}"
        ".metric span{display:block;font-size:11px;color:var(--muted);margin-bottom:3px}.metric strong{font-size:17px}.card-body{margin-top:10px;line-height:1.75}.card-body p{margin:8px 0;font-size:14px}"
        ".topnav{display:flex;gap:10px;margin:16px 0 28px}.topnav a{padding:8px 14px;border-radius:9px;background:var(--brand);color:#fff;text-decoration:none;font-size:14px}.note{margin:16px 0;padding:14px 18px;border-radius:10px;background:#fff8dc;border:1px solid #dfc578;color:#665629;font-size:13px;line-height:1.7}"
        ".footer{margin-top:50px;padding-top:24px;border-top:1px solid var(--line);color:var(--muted);font-size:13px;line-height:1.8}@media(max-width:680px){.card-metrics{grid-template-columns:repeat(2,1fr)}.shell{width:100%;max-width:100vw;padding:24px 14px 40px;overflow-x:hidden}table{display:none}.mobile-summary{display:block;width:340px;max-width:100%}.mobile-result{width:100%;max-width:100%;padding:14px;margin:10px 0;border:1px solid var(--line);border-radius:12px;background:var(--card)}.mobile-result h3{margin:0 0 10px;font-size:14px;line-height:1.5;overflow-wrap:anywhere}.mobile-result p{display:grid;grid-template-columns:1fr auto;gap:14px;margin:7px 0;color:var(--muted);font-size:14px}.mobile-result strong{color:var(--ink);font-variant-numeric:tabular-nums}.mobile-result strong.positive{color:#1a7a3a}.mobile-result strong.negative{color:#b53636}}"
    )
    return (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>再平衡策略研究</title><style>{css}</style></head><body><main class='shell'>"
        "<h1>再平衡策略对比研究</h1>"
        "<p class='sub'><b>研究问题：</b>沪深300、中证500、中证1000 之间是否需要再平衡，以及动量与再平衡如何折中。<br>"
        f"<b>基准：</b>自然漂移（年化 {drift_twr * 100:+.2f}%）</p>"
        "<nav class='topnav'><a href='../index.html'>← 返回首页</a></nav>"
        "<h2>总览</h2><table><thead><tr><th>策略</th><th>年化 TWR</th><th>超额收益</th><th>Sharpe</th><th>最大回撤</th><th>换手率</th></tr></thead>"
        f"<tbody>{rows}</tbody></table><div class='mobile-summary'>{mobile_rows}</div>"
        f"<p class='note'><b>超额收益</b> = 策略年化 TWR − 自然漂移 baseline（{drift_twr * 100:+.2f}%）。历史收益不代表未来表现。</p>"
        f"<h2>策略说明</h2>{cards}"
        "<h2>数据与方法</h2><div class='card'><div class='card-body'>"
        "<p><b>收益口径：</b>TWR，排除资金流入流出影响；XIRR 仅用于投资者现金流体验。</p>"
        "<p><b>执行假设：</b>信号在观察日收盘后形成，下一共同交易日执行；卖出先于买入；成本双边计入。</p>"
        "<p><b>动量信号：</b>12-1/6-1/3-1 收益按 0.5/0.3/0.2 加权，并做波动率调整。</p>"
        "<p><b>限制：</b>仅三个高度相关指数，样本少，多重检验会放大偶然性；页面不构成投资建议。</p>"
        "</div></div><div class='footer'>中证指数 · AkShare · 公众号：<strong>炼金魔女手记</strong></div>"
        "</main></body></html>"
    )
