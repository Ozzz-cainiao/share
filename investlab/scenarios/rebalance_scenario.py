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
    parser.add_argument("--output-dir", default="output/rebalance", help="Output directory")


def run(args) -> int:
    import math
    from pathlib import Path

    import numpy as np
    import pandas as pd

    from investlab.data import fetch_price_series, select_assets
    from investlab.engine import run_multi_asset_backtest
    from investlab.utils import xirr

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    equity_dir = output_dir / "equity_curves"
    equity_dir.mkdir(parents=True, exist_ok=True)

    # Load prices for all assets into a DataFrame
    asset_keys = [x.strip() for x in args.assets.split(",") if x.strip()]
    assets = select_assets(asset_keys)
    price_series_dict = {}
    for asset in assets:
        prices = fetch_price_series(asset, args.start, args.end)
        if len(prices) < 252:
            print(f"WARNING: {asset.key} has < 1 year of data ({len(prices)} days), skipping")
            continue
        price_series_dict[asset.key] = prices

    if len(price_series_dict) < 1:
        print("ERROR: No assets with sufficient data")
        return 1

    prices_df = pd.DataFrame(price_series_dict)
    # Save price data
    prices_df.to_csv(output_dir / "prices.csv", encoding="utf-8-sig")

    # Build strategies
    strategies = build_rebalance_strategies(args)
    print(f"Running {len(strategies)} strategies on {len(price_series_dict)} assets...")

    # Run backtests
    summaries: list[dict] = []
    baseline_xirr: float | None = None

    for strat in strategies:
        result = run_multi_asset_backtest(
            prices_df=prices_df,
            strategy=strat,
            monthly_contribution=args.monthly,
            annual_cash_rate=args.cash_rate,
            fee_rate=args.fee_rate,
        )

        # Save equity curve
        result.equity_curve.to_csv(
            equity_dir / f"{strat.name}_equity.csv", encoding="utf-8-sig"
        )

        # Compute metrics
        daily_returns = result.equity_curve.pct_change().dropna()
        ann_return = float(daily_returns.mean() * 252.0) if not daily_returns.empty else math.nan
        ann_vol = float(daily_returns.std(ddof=0) * np.sqrt(252.0)) if not daily_returns.empty else math.nan
        sharpe = (ann_return - args.cash_rate) / ann_vol if ann_vol and ann_vol > 1e-12 else math.nan

        span_days = (result.equity_curve.index[-1] - result.equity_curve.index[0]).days
        years = span_days / 365.25 if span_days > 0 else math.nan
        cagr = (result.final_value / result.total_contribution) ** (1.0 / years) - 1.0 if years and years > 0 and result.total_contribution > 0 else math.nan

        strat_xirr = xirr(result.cashflows)

        # Track baseline
        if strat.name == "noreb":
            baseline_xirr = strat_xirr

        # Combined asset key for multi-asset results
        combined_key = "+".join(sorted(price_series_dict.keys()))

        summaries.append({
            "asset_key": combined_key,
            "asset_name": " + ".join(a.name for a in assets),
            "strategy_name": strat.name,
            "strategy_display_name": strat.display_name,
            "final_value": result.final_value,
            "total_contribution": result.total_contribution,
            "xirr": strat_xirr,
            "cagr": cagr,
            "max_drawdown": float((result.equity_curve / result.equity_curve.cummax() - 1.0).min()) if not result.equity_curve.empty else math.nan,
            "ann_return": ann_return,
            "ann_vol": ann_vol,
            "sharpe": sharpe,
            "avg_cash_ratio": result.avg_cash_ratio,
            "trade_count": result.trade_count,
            "xirr_excess": 0.0,
        })

    # Compute xirr_excess
    for s in summaries:
        s["xirr_excess"] = s["xirr"] - baseline_xirr if baseline_xirr is not None else 0.0

    # T13: CSV output
    summary_df = pd.DataFrame(summaries)
    summary_df = summary_df.sort_values(["strategy_name"], ignore_index=True)

    # Long table
    long_path = output_dir / "summary_long.csv"
    summary_df.to_csv(long_path, index=False, encoding="utf-8-sig")

    # Wide XIRR table
    xirr_pivot = summary_df.pivot_table(
        index=["asset_key", "asset_name"],
        columns="strategy_display_name",
        values="xirr",
    ).reset_index()
    wide_path = output_dir / "summary_xirr_wide.csv"
    xirr_pivot.to_csv(wide_path, index=False, encoding="utf-8-sig")

    # Wide excess table
    excess_pivot = summary_df.pivot_table(
        index=["asset_key", "asset_name"],
        columns="strategy_display_name",
        values="xirr_excess",
    ).reset_index()
    excess_path = output_dir / "summary_xirr_excess_wide.csv"
    excess_pivot.to_csv(excess_path, index=False, encoding="utf-8-sig")

    print(f"Rebalance backtest complete. {len(summaries)} strategy results.")
    print(f"  Summary (long):   {long_path}")
    print(f"  Summary (xirr):   {wide_path}")
    print(f"  Summary (excess): {excess_path}")
    build_html_report(summaries, str(output_dir / "rebalance_comparison.html"))
    return 0



def build_html_report(summaries: list[dict], output_path: str) -> None:
    """Generate self-contained HTML comparison report."""
    import html as html_mod

    if not summaries:
        html_content = "<html><body><p>No results to display.</p></body></html>"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        return

    # Sort by XIRR descending
    sorted_summaries = sorted(summaries, key=lambda s: s.get("xirr", -999), reverse=True)

    rows = ""
    for s in sorted_summaries:
        xirr = s.get("xirr", float("nan"))
        excess = s.get("xirr_excess", 0.0)
        sharpe = s.get("sharpe", float("nan"))
        mdd = s.get("max_drawdown", float("nan"))
        trades = s.get("trade_count", 0)
        final_v = s.get("final_value", 0.0)
        contrib = s.get("total_contribution", 0.0)
        total_ret = (final_v / contrib - 1.0) * 100 if contrib > 0 else 0.0

        xirr_str = f"{xirr*100:+.2f}%" if not (xirr != xirr) else "N/A"
        excess_str = f"{excess*100:+.2f}%" if not (excess != excess) else "N/A"
        sharpe_str = f"{sharpe:.2f}" if not (sharpe != sharpe) else "N/A"
        mdd_str = f"{mdd*100:.1f}%" if not (mdd != mdd) else "N/A"

        cls = "positive" if excess > 0 else "negative"

        rows += f"""<tr>
            <td>{html_mod.escape(s["strategy_display_name"])}</td>
            <td class="num">{xirr_str}</td>
            <td class="num {cls}">{excess_str}</td>
            <td class="num">{sharpe_str}</td>
            <td class="num">{mdd_str}</td>
            <td class="num">{trades}</td>
            <td class="num">{total_ret:+.1f}%</td>
        </tr>"""

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>再平衡策略对比报告</title>
<style>
:root{{--ink:#26304a;--muted:#68758b;--line:#dce2ed;--paper:#f5f7fb;--card:#fff}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.shell{{max-width:960px;margin:auto;padding:44px 28px 60px}}
h1{{margin:8px 0 4px;font:600 34px Georgia,"Songti SC",serif}}
.subtitle{{color:var(--muted);font-size:15px;margin-bottom:28px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(35,45,75,.06)}}
th,td{{padding:12px 16px;text-align:left;border-bottom:1px solid var(--line);font-size:14px}}
th{{background:#eef2f8;font-weight:600;color:var(--ink);font-size:13px}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.positive{{color:#1a7a3a;font-weight:600}}
.negative{{color:#b53636}}
tr:hover{{background:#f8fafd}}
.footer{{margin-top:40px;padding-top:20px;border-top:1px solid var(--line);color:var(--muted);font-size:13px;line-height:1.7}}
.note{{margin:16px 0;padding:12px 16px;border-radius:10px;background:#fff8dc;border:1px solid #dfc578;color:#665629;font-size:13px;line-height:1.6}}
</style>
</head>
<body>
<main class="shell">
<h1>再平衡策略对比报告</h1>
<p class="subtitle">等权再平衡 vs 动量叠加 · {len(sorted_summaries)} 个策略</p>
<p class="note">超额收益 = 策略 XIRR − 不调仓 baseline XIRR。正数表示再平衡/动量策略优于买入持有。</p>
<table>
<thead><tr>
<th>策略</th>
<th>XIRR</th>
<th>超额收益</th>
<th>Sharpe</th>
<th>最大回撤</th>
<th>交易次数</th>
<th>总收益</th>
</tr></thead>
<tbody>{rows}</tbody>
</table>
<div class="footer">
数据来源：中证指数（全收益口径），经 AkShare 获取。<br>
历史收益不代表未来表现。本页面仅用于数据研究与方法展示，不构成投资建议。<br>
更多长期投资研究，欢迎关注公众号：<strong>炼金魔女手记</strong>
</div>
</main>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


# ---- Scenario registration ----
from investlab.scenarios.registry import SCENARIO_REGISTRY, ScenarioEntry

REBALANCE_SCENARIO = ScenarioEntry(
    name="rebalance",
    description="Multi-asset rebalancing backtest (equal-weight, momentum filter, momentum weight)",
    add_arguments=add_arguments,
    run=run,
)
SCENARIO_REGISTRY.register(REBALANCE_SCENARIO)
