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

    # Generate self-contained HTML report
    import html as html_mod
    drift_twr = next((r['ann_return_twr'] for r in results if r.get('strategy_name') == 'drift'), 0)
    html_rows = ""
    for r in sorted(results, key=lambda x: x.get('ann_return_twr', -999), reverse=True):
        twr = r.get('ann_return_twr', 0)
        excess = twr - drift_twr
        cls = "positive" if excess > 0 else "negative"
        html_rows += f"<tr><td>{html_mod.escape(str(r.get('strategy_display', r.get('strategy_name',''))))}</td><td class='num'>{twr*100:+.2f}%</td><td class='num {cls}'>{excess*100:+.2f}%</td><td class='num'>{r.get('sharpe_twr',0):.3f}</td><td class='num'>{r.get('max_drawdown_twr',0)*100:.1f}%</td><td class='num'>{r.get('avg_turnover',0)*100:.1f}%</td></tr>"
    report_html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>再平衡策略对比</title><style>:root{{--ink:#26304a;--muted:#68758b;--line:#dce2ed;--paper:#f5f7fb}}*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}.shell{{max-width:960px;margin:auto;padding:44px 28px 60px}}h1{{font:600 34px Georgia,"Songti SC",serif}}.sub{{color:var(--muted);font-size:15px;margin-bottom:24px}}table{{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(35,45,75,.06)}}th,td{{padding:12px 16px;border-bottom:1px solid var(--line);font-size:14px}}th{{background:#eef2f8;font-weight:600;font-size:13px}}.num{{text-align:right;font-variant-numeric:tabular-nums}}.positive{{color:#1a7a3a;font-weight:600}}.negative{{color:#b53636}}tr:hover{{background:#f8fafd}}.footer{{margin-top:40px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:13px}}.note{{margin:16px 0;padding:12px 16px;border-radius:10px;background:#fff8dc;border:1px solid #dfc578;color:#665629;font-size:13px}}.topnav a{{padding:8px 14px;border-radius:9px;background:#405477;color:#fff;text-decoration:none;font-size:14px}}</style></head><body><main class="shell"><h1>再平衡策略对比</h1><p class="sub">沪深300+中证500+中证1000 · 一次性投入 · TWR口径</p><div class="topnav"><a href="../index.html">← 返回首页</a></div><p class="note">超额收益=策略TWR−自然漂移baseline({drift_twr*100:+.2f}%)</p><table><thead><tr><th>策略</th><th>年化TWR</th><th>超额收益</th><th>Sharpe</th><th>最大回撤</th><th>换手率</th></tr></thead><tbody>{html_rows}</tbody></table><div class="footer">中证全收益指数(AkShare) · 历史收益不代表未来 · 公众号:炼金魔女手记</div></main></body></html>"""
    (output_dir / "rebalance_comparison.html").write_text(report_html, encoding="utf-8")
    print(f"  HTML report: {output_dir / 'rebalance_comparison.html'}")

    return 0


from investlab.scenarios.registry import SCENARIO_REGISTRY, ScenarioEntry

REBALANCE_SCENARIO = ScenarioEntry(
    name="rebalance",
    description="Multi-asset rebalancing backtest (equal-weight, momentum filter, momentum weight)",
    add_arguments=add_arguments,
    run=run,
)
SCENARIO_REGISTRY.register(REBALANCE_SCENARIO)
