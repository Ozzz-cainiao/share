from __future__ import annotations

from dataclasses import dataclass

from investlab.models import MultiAssetStrategyProtocol


def parse_rebalance_freqs(freq_str: str) -> list[str]:
    """Parse comma-separated frequencies. Defaults to all three."""
    valid = {"monthly", "quarterly", "annual"}
    if not freq_str.strip():
        return ["monthly", "quarterly", "annual"]
    freqs = [f.strip().lower() for f in freq_str.split(",") if f.strip()]
    for f in freqs:
        if f not in valid:
            raise ValueError(f"Invalid frequency: {f!r}. Valid: {sorted(valid)}")
    return freqs


def parse_momentum_lookbacks(lb_str: str) -> list[int]:
    """Parse comma-separated ints. Defaults to [3, 6, 12]."""
    if not lb_str.strip():
        return [3, 6, 12]
    lookbacks: list[int] = []
    for token in lb_str.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            lb = int(token)
        except ValueError:
            raise ValueError(f"Invalid momentum lookback: {token!r}. Must be integer.")
        if lb < 1:
            raise ValueError(f"Momentum lookback must be >= 1, got {lb}")
        lookbacks.append(lb)
    return lookbacks


def parse_thresholds(th_str: str) -> list[float]:
    """Parse comma-separated thresholds. Defaults to [0.05, 0.10]."""
    if not th_str.strip():
        return [0.05, 0.10]
    thresholds: list[float] = []
    for token in th_str.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            t = float(token)
        except ValueError:
            raise ValueError(f"Invalid threshold: {token!r}. Must be float.")
        if t <= 0 or t >= 1:
            raise ValueError(f"Threshold must be in (0, 1), got {t}")
        thresholds.append(t)
    return thresholds


def build_rebalance_strategies(args) -> list[MultiAssetStrategyProtocol]:
    """Build strategy instances from CLI args."""
    from investlab.strategies import (
        EqualWeightCalendarStrategy,
        MomentumFilterRebalanceStrategy,
        MomentumWeightStrategy,
        NoRebalanceStrategy,
        ThresholdRebalanceStrategy,
    )

    freqs = parse_rebalance_freqs(getattr(args, 'rebalance_freqs', ''))
    lookbacks = parse_momentum_lookbacks(getattr(args, 'momentum_lookbacks', ''))
    thresholds = parse_thresholds(getattr(args, 'thresholds', ''))
    momentum_modes = getattr(args, 'momentum_modes', 'filter,weight')
    modes = [m.strip().lower() for m in momentum_modes.split(",") if m.strip()]
    top_n_values = [int(x.strip()) for x in getattr(args, 'momentum_top_n', '2').split(",") if x.strip()]

    strategies: list[MultiAssetStrategyProtocol] = []

    # Baseline
    strategies.append(NoRebalanceStrategy())

    # Calendar rebalance
    for freq in freqs:
        strategies.append(EqualWeightCalendarStrategy(frequency=freq))

    # Threshold rebalance
    for th in thresholds:
        strategies.append(ThresholdRebalanceStrategy(threshold=th))

    # Momentum filter
    if "filter" in modes:
        for freq in freqs:
            for lb in lookbacks:
                strategies.append(MomentumFilterRebalanceStrategy(frequency=freq, momentum_lookback=lb))

    # Momentum weight
    if "weight" in modes:
        for lb in lookbacks:
            for tn in top_n_values:
                strategies.append(MomentumWeightStrategy(momentum_lookback=lb, top_n=tn))

    return strategies


# ---- Scenario entry point ----

def add_arguments(parser) -> None:
    parser.add_argument("--start", default="2015-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default="2025-12-31", help="End date YYYY-MM-DD")
    parser.add_argument(
        "--assets",
        default="H00300,H00905,H00852",
        help="Comma-separated asset keys",
    )
    parser.add_argument(
        "--rebalance-freqs",
        default="monthly,quarterly,annual",
        help="Comma-separated: monthly,quarterly,annual",
    )
    parser.add_argument(
        "--thresholds",
        default="0.05,0.10",
        help="Comma-separated deviation thresholds (e.g. 0.05,0.10)",
    )
    parser.add_argument(
        "--momentum-lookbacks",
        default="3,6,12",
        help="Comma-separated lookback months",
    )
    parser.add_argument(
        "--momentum-modes",
        default="filter,weight",
        help="Comma-separated: filter,weight",
    )
    parser.add_argument(
        "--momentum-top-n",
        default="2",
        help="Comma-separated top-N values for MomentumWeightStrategy",
    )
    parser.add_argument("--monthly", type=float, default=1.0, help="Monthly contribution")
    parser.add_argument("--cash-rate", type=float, default=0.02, help="Annual cash yield")
    parser.add_argument("--fee-rate", type=float, default=0.0003, help="Single-side fee rate")
    parser.add_argument("--initial-capital", type=float, default=1.0, help="Lump-sum initial capital (0 for contribution-only)")
    parser.add_argument("--panel", default="index", choices=["index", "etf", "both"], help="Research panel")
    parser.add_argument("--output-dir", default="output/rebalance", help="Output directory")



def generate_rich_report(results, output_dir, drift_twr):
    """Generate methodology-rich HTML report with strategy cards."""
    import html as html_mod
    
    strategies_info = {
        "drift": ("自然漂移（不调仓）", "drift",
            "2012年初将资金等分三份买入沪深300、中证500、中证1000后<b>永不调仓</b>。任其随市场涨跌自然漂移，赢家越滚越大、输家越缩越小。这是最懒的策略，也是所有策略的对比基准。",
            "权重随市场自由漂移，无固定比例。牛市末尾可能极度集中于单一指数。"),
        "ew_monthly": ("等权月度再平衡", "calendar",
            "每月月初<b>强制恢复等权</b>（各1/3）。卖出一部分赢家、买入一部分输家。调仓频率最高、交易磨损最大，但在震荡市中能持续收割波动收益。",
            "始终维持 33%/33%/33% 等权，偏离后立即拉回。相当于机械式高抛低吸。"),
        "ew_quarterly": ("等权季度再平衡", "calendar",
            "每季度初（1/4/7/10月）恢复等权。比月度少一些交易成本，比年度更及时响应市场变化。",
            "大部分时间围绕 33%/33%/33% 波动，季度末强制拉回。"),
        "ew_annual": ("等权年度再平衡", "calendar",
            "每年1月恢复等权。交易成本最低，允许赢家充分奔跑一整年。在趋势市中优于高频再平衡。",
            "一年调一次，年中权重可大幅偏离。"),
        "thresh_5": ("阈值再平衡（5%偏离）", "threshold",
            "仅在任一指数权重偏离等权<b>超过 5 个百分点</b>时才调仓（如某指数涨到 38%+）。平衡了交易成本与风险控制。",
            "偏离超过 ±5pp 时拉回等权，平时不操作。"),
        "thresh_10": ("阈值再平衡（10%偏离）", "threshold",
            "偏离超过 <b>10 个百分点</b>才调仓。极度容忍漂移，几乎等同于不调仓。",
            "仅在极端偏离时出手，其余时间放任漂移。"),
        "inv_vol": ("逆波动率加权", "inverse_vol",
            "每月根据过去 <b>63 个交易日</b>的波动率反向分配权重：<b>波动越小的指数权重越大</b>，波动越大的权重越小（限制在 10%-65%）。原理是低波动资产往往风险调整后收益更优（低波动异象）。",
            "动态变化：稳定期三指数接近等权，剧烈分化时资金向低波动指数倾斜。"),
        "blend_0.50_5bp": ("固定混合（λ=0.5 / 5bp 免调带）", "blend",
            "将等权目标与动量排名目标按 <b>50/50 混合</b>。动量排名基于过去 12/6/3 个月收益加权打分，波动率调整后排名，前两名分获 60%/30% 权重。偏离不超过 5 个百分点不调仓。",
            "一半资金遵循等权纪律，一半追逐近期强势指数。"),
        "regime_adaptive": ("结构牛市自适应", "regime",
            "根据市场状态自动切换参数：<b>结构牛市</b>（趋势向上 + 指数间收益分化大）→ 偏向动量（λ=0.75），<b>普通上升</b>→ 均衡（λ=0.50），<b>下跌/震荡</b>→ 偏向再平衡（λ=0.25）。结构牛市中动量领先者的卖出容忍度放宽到 15pp。",
            "市场好时让赢家跑，市场差时严格再平衡。全程动态调整。"),
        "fixed_H0030050_H0090530_H0085220": ("固定比例·大盘倾斜 50/30/20", "fixed_ratio",
            "初始按<b>50%沪深300 + 30%中证500 + 20%中证1000</b>买入后永不调仓。近似市值加权，大盘主导。",
            "50% 沪深300 / 30% 中证500 / 20% 中证1000，买入后不调整。"),
        "fixed_rebal_H0030050_H0090530_H0085220": ("固定比例月度再平衡·大盘倾斜", "fixed_ratio",
            "每月恢复<b>50/30/20</b>目标比例。大盘倾斜 + 月度纪律。",
            "每月强制恢复 50/30/20。"),
        "fixed_H0085220_H0090530_H0030050": ("固定比例·小盘倾斜 20/30/50", "fixed_ratio",
            "初始按<b>20%沪深300 + 30%中证500 + 50%中证1000</b>买入。大幅超配小盘。",
            "20% 沪深300 / 30% 中证500 / 50% 中证1000。"),
        "fixed_rebal_H0085220_H0090530_H0030050": ("固定比例月度再平衡·小盘倾斜", "fixed_ratio",
            "每月恢复<b>20/30/50</b>目标。超配小盘 + 月度纪律。",
            "每月强制恢复 20/30/50。"),
        "fixed_H0030040_H0085240_H0090520": ("固定比例·哑铃 40/20/40", "fixed_ratio",
            "初始按<b>40%沪深300 + 20%中证500 + 40%中证1000</b>买入。两头重中间轻。",
            "40% 沪深300 / 20% 中证500 / 40% 中证1000。"),
        "fixed_rebal_H0030040_H0085240_H0090520": ("固定比例月度再平衡·哑铃", "fixed_ratio",
            "每月恢复<b>40/20/40</b>目标。哑铃配置 + 月度再平衡。",
            "每月强制恢复 40/20/40。"),

    }

    cards = ""
    for r in sorted(results, key=lambda x: x.get('ann_return_twr', -999), reverse=True):
        name = r.get('strategy_name', '')
        info = strategies_info.get(name)
        if not info:
            continue
        display, family, desc, alloc = info
        twr = r.get('ann_return_twr', 0)
        excess = twr - drift_twr
        cls = "positive" if excess > 0 else "negative"
        sign = "+" if excess > 0 else ""
        cards += f"""<div class="card"><div class="card-header"><span class="badge">{family}</span><h3>{html_mod.escape(display)}</h3></div>
<div class="card-metrics"><div class="metric"><span>TWR</span><strong>{twr*100:+.2f}%</strong></div><div class="metric"><span>超额</span><strong class="{cls}">{sign}{excess*100:.2f}%</strong></div>
<div class="metric"><span>Sharpe</span><strong>{r.get('sharpe_twr',0):+.3f}</strong></div><div class="metric"><span>最大回撤</span><strong>{r.get('max_drawdown_twr',0)*100:.1f}%</strong></div></div>
<div class="card-body"><p><b>策略逻辑：</b>{desc}</p><p><b>资产配置：</b>{alloc}</p></div></div>"""

    rows = ""
    for r in sorted(results, key=lambda x: x.get('ann_return_twr', -999), reverse=True):
        twr = r.get('ann_return_twr', 0); excess = twr - drift_twr
        cls = "positive" if excess > 0 else "negative"; sign = "+" if excess > 0 else ""
        rows += f"<tr><td>{html_mod.escape(str(r.get('strategy_display', r.get('strategy_name',''))))}</td><td class='num'>{twr*100:+.2f}%</td><td class='num {cls}'>{sign}{excess*100:.2f}%</td><td class='num'>{r.get('sharpe_twr',0):+.3f}</td><td class='num'>{r.get('max_drawdown_twr',0)*100:.1f}%</td><td class='num'>{r.get('avg_turnover',0)*100:.1f}%</td></tr>"

    css = ":root{--ink:#26304a;--muted:#68758b;--line:#dce2ed;--paper:#f5f7fb;--card:#fff;--brand:#405477}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif}.shell{max-width:960px;margin:auto;padding:44px 28px 60px}h1{margin:8px 0 4px;font:600 34px Georgia,'Songti SC',serif}h2{margin:32px 0 12px;font-size:22px}.sub{color:var(--muted);font-size:15px;margin-bottom:24px;line-height:1.7}table{width:100%;border-collapse:collapse;background:var(--card);border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(35,45,75,.06);margin:18px 0}th,td{padding:12px 16px;text-align:left;border-bottom:1px solid var(--line);font-size:14px}th{background:#eef2f8;font-weight:600;font-size:13px}.num{text-align:right;font-variant-numeric:tabular-nums}.positive{color:#1a7a3a;font-weight:600}.negative{color:#b53636}tr:hover{background:#f8fafd}.card{padding:22px;margin:14px 0;border:1px solid var(--line);border-radius:14px;background:var(--card);box-shadow:0 4px 18px rgba(35,45,75,.04)}.card-header{display:flex;align-items:center;gap:10px;margin-bottom:12px}.badge{display:inline-block;padding:3px 10px;border-radius:6px;font-size:11px;font-weight:600;background:#eef2f8;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}.card-header h3{margin:0;font-size:18px}.card-metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:12px 0}.metric{padding:10px;background:#f8fafd;border-radius:8px;text-align:center}.metric span{display:block;font-size:11px;color:var(--muted);margin-bottom:3px}.metric strong{font-size:17px}.card-body{margin-top:10px;line-height:1.75;color:var(--ink)}.card-body p{margin:8px 0;font-size:14px}.topnav{display:flex;gap:10px;margin:16px 0 28px}.topnav a{padding:8px 14px;border-radius:9px;background:var(--brand);color:#fff;text-decoration:none;font-size:14px}.footer{margin-top:50px;padding-top:24px;border-top:1px solid var(--line);color:var(--muted);font-size:13px;line-height:1.8}.note{margin:16px 0;padding:14px 18px;border-radius:10px;background:#fff8dc;border:1px solid #dfc578;color:#665629;font-size:13px;line-height:1.7}@media(max-width:680px){.card-metrics{grid-template-columns:repeat(2,1fr)}.shell{padding:24px 14px 40px}}"

    html = f"<!doctype html><html lang=zh-CN><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>再平衡策略研究</title><style>{css}</style></head><body><main class=shell><h1>再平衡策略对比研究</h1><p class=sub><b>研究问题：</b>沪深300、中证500、中证1000 之间需要再平衡吗？动量策略在结构牛市中是否反而有害？<br><b>数据：</b>2012-2025 年中证全收益指数 · 一次性投入 · TWR 口径<br><b>基准：</b>自然漂移（年化 {drift_twr*100:+.2f}%）</p><nav class=topnav><a href=../index.html>← 返回首页</a></nav><h2>📊 总览</h2><table><thead><tr><th>策略</th><th>年化 TWR</th><th>超额收益</th><th>Sharpe</th><th>最大回撤</th><th>换手率</th></tr></thead><tbody>{rows}</tbody></table><p class=note>📌 <b>超额收益</b> = 策略年化 TWR − 自然漂移 baseline（{drift_twr*100:+.2f}%）。绿色正数 = 优于不调仓，红色负数 = 跑输。</p><h2>📖 策略详解</h2>{cards}<h2>📐 数据与方法</h2><div class=card><div class=card-body><p><b>数据来源：</b>中证指数有限公司全收益指数，经 AkShare 获取。</p><p><b>收益口径：</b>TWR（时间加权收益率），排除资金流入流出影响。</p><p><b>交易执行：</b>每月初先卖出超配资产获得现金，再买入低配资产。双边万分之三手续费。</p><p><b>动量信号：</b>12-1/6-1/3-1 月收益加权（0.5/0.3/0.2），经波动率调整后排名。跳过最近 1 月避免反转噪音。</p><p><b>结构牛市判定：</b>等权组合高于 200 日均线、60 日均线上升、收益离散度超历史中位数。无前视偏差。</p><p><b>样本外验证：</b>滚动年折叠（5年训练→2年验证→1年测试），验证集最大回撤劣于基准 5pp 淘汰。</p><p><b>限制：</b>仅三个指数、相关性高、统计功效有限；不构成投资建议。</p></div></div><div class=footer>中证指数 · AkShare · 公众号：<strong>炼金魔女手记</strong><br>历史收益不代表未来表现</div></main></body></html>"

    (output_dir / "rebalance_comparison.html").write_text(html, encoding="utf-8")
    print(f"  HTML report: {output_dir / 'rebalance_comparison.html'}")


def run(args) -> int:
    import json, math
    from pathlib import Path
    import numpy as np
    import pandas as pd
    from investlab.data import select_assets
    from investlab.rebalance.data import build_index_panel, write_manifest
    from investlab.rebalance.engine import run_multi_asset_backtest
    from investlab.rebalance.experiment import run_full_sample, run_walk_forward
    from investlab.rebalance.metrics import compute_twr_metrics
    from investlab.rebalance.statistics import parameter_surface
    from investlab.rebalance.strategies import (
        CalendarEqualWeight, DriftStrategy, FixedBlendStrategy,
        FixedRatioStrategy, FixedRatioRebalanceStrategy,
        InverseVolatility, RegimeAdaptiveStrategy, ThresholdEqualWeight,
    )

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df, meta = build_index_panel(args.start, args.end)
    write_manifest(meta, output_dir)

    strategies = [
        DriftStrategy(),
        CalendarEqualWeight(frequency="monthly"),
        CalendarEqualWeight(frequency="quarterly"),
        CalendarEqualWeight(frequency="annual"),
        ThresholdEqualWeight(threshold=0.05),
        ThresholdEqualWeight(threshold=0.10),
        InverseVolatility(),
        FixedBlendStrategy(lam=0.50, band=0.05),
        RegimeAdaptiveStrategy(),
        FixedRatioStrategy(target={"H00300": 0.50, "H00905": 0.30, "H00852": 0.20}),
        FixedRatioRebalanceStrategy(target={"H00300": 0.50, "H00905": 0.30, "H00852": 0.20}),
        FixedRatioStrategy(target={"H00300": 0.20, "H00905": 0.30, "H00852": 0.50}),
        FixedRatioRebalanceStrategy(target={"H00300": 0.20, "H00905": 0.30, "H00852": 0.50}),
        FixedRatioStrategy(target={"H00300": 0.40, "H00905": 0.20, "H00852": 0.40}),
        FixedRatioRebalanceStrategy(target={"H00300": 0.40, "H00905": 0.20, "H00852": 0.40}),
    ]

    results = run_full_sample(df, strategies, initial_capital=getattr(args, 'initial_capital', 1.0),
                              annual_cash_rate=args.cash_rate, fee_rate=args.fee_rate)

    candidates = [DriftStrategy()] + [CalendarEqualWeight(frequency=f) for f in ["monthly", "quarterly"]] +         [FixedBlendStrategy(lam=l, band=0.05) for l in [0.25, 0.50, 0.75]]
    oos_results, folds = run_walk_forward(df, candidates, DriftStrategy(),
                                          initial_capital=getattr(args, 'initial_capital', 1.0),
                                          annual_cash_rate=args.cash_rate, fee_rate=args.fee_rate)

    surface_df = parameter_surface(results)

    summary_df = pd.DataFrame(results)
    summary_df.to_csv(output_dir / "summary_full_sample.csv", index=False, encoding="utf-8-sig")

    if oos_results:
        pd.DataFrame(oos_results).to_csv(output_dir / "summary_oos.csv", index=False, encoding="utf-8-sig")
    if folds:
        fold_rows = [{"fold": f.fold, "train_start": f.train_start, "train_end": f.train_end,
                      "val_start": f.val_start, "val_end": f.val_end,
                      "test_start": f.test_start, "test_end": f.test_end,
                      "selected_id": f.selected_id, "reason": f.selection_reason} for f in folds]
        pd.DataFrame(fold_rows).to_csv(output_dir / "fold_selections.csv", index=False, encoding="utf-8-sig")
    if len(surface_df) > 0:
        surface_df.to_csv(output_dir / "parameter_surface.csv", index=False, encoding="utf-8-sig")

    catalog = [{"id": s.name, "display_name": s.display_name, "family": getattr(s, "family", "")} for s in strategies]
    with open(output_dir / "strategy_catalog.json", "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"Rebalance research complete. {len(results)} strategies, {len(folds)} walk-forward folds.")
    print(f"  Full sample: {output_dir / 'summary_full_sample.csv'}")
    if oos_results:
        print(f"  OOS:         {output_dir / 'summary_oos.csv'}")

    drift_twr = next((r["ann_return_twr"] for r in results if r.get("strategy_name") == "drift"), 0)
    generate_rich_report(results, output_dir, drift_twr)

    return 0


from investlab.scenarios.registry import SCENARIO_REGISTRY, ScenarioEntry

REBALANCE_SCENARIO = ScenarioEntry(
    name="rebalance",
    description="Multi-asset rebalancing backtest (equal-weight, momentum filter, momentum weight)",
    add_arguments=add_arguments,
    run=run,
)
SCENARIO_REGISTRY.register(REBALANCE_SCENARIO)
