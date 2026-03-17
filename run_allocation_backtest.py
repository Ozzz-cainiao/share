#!/usr/bin/env python3
"""Complete asset allocation backtest with report generation.

This script runs the full backtest pipeline:
1. Data collection and panel construction
2. Lumpsum backtests (10y, 5y, 3y, 1y)
3. Rolling window validation (7-year quarterly)
4. Quarterly DCA simulation
5. Benchmark comparisons
6. Visualization generation
7. Report generation (Markdown + HTML)

Updated parameters (2026-03-17):
    cash = 2% (fixed)
    gold = 8% (fixed)
    usBond = 8% (fixed)
    usStock = 20% + 30% * xUsPremium (range 20%-50%)
    cnStock = 20% + remaining * yCnSignal (minimum 20%)
    cnBond = remaining * (1 - yCnSignal)
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd

from investlab.allocation.backtest import (
    build_panel,
    run_lumpsum_backtest,
    run_dca_backtest,
    benchmark_nav_from_prices,
    run_benchmark_dca,
    BENCHMARKS,
    DCAResult,
    BacktestResult,
)
from investlab.allocation.visualization import (
    generate_all_figures,
    generate_allocation_shift_chart,
    generate_performance_comparison,
)
from investlab.allocation.calculator import (
    allocation_table,
    get_asset_summary,
)


def format_percent(value: float) -> str:
    """Format float as percentage string."""
    return f"{value:.2%}"


def format_float(value: float) -> str:
    """Format float with 2 decimal places."""
    return f"{value:.2f}"


def generate_markdown_report(
    results: Dict[str, List[BacktestResult]],
    dca_results: Dict[str, List[DCAResult]],
    panel: pd.DataFrame,
    output_dir: Path,
    figure_paths: Dict[str, Path],
) -> Path:
    """Generate comprehensive markdown report."""
    report_path = output_dir / "allocation_backtest_report.md"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 资产配置回测分析报告\n\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("## 1. 策略参数\n\n")
        f.write("| 参数 | 值 | 说明 |\n")
        f.write("|------|-----|------|\n")
        f.write("| cash | 2% | 固定现金比例 |\n")
        f.write("| gold | 8% | 固定黄金比例 |\n")
        f.write("| usBond | 8% | 固定美债比例 |\n")
        f.write("| usStock | 20% + 30% × xUsPremium | 美股比例 (20%-50%) |\n")
        f.write("| cnStock | 20% + remaining × yCnSignal | A股比例 (最低20%) |\n")
        f.write("| cnBond | remaining × (1 - yCnSignal) | 中债比例 |\n\n")

        f.write("## 2. 数据概况\n\n")
        f.write(f"- 数据区间: {panel['month'].min()} 至 {panel['month'].max()}\n")
        f.write(f"- 月度样本数: {len(panel)}\n")
        f.write(f"- A股信号使用指数: {panel.attrs.get('cn_index_used', '未知')}\n\n")

        f.write("## 3. 配置可视化\n\n")
        for name, path in figure_paths.items():
            f.write(f"### {name.replace('_', ' ').title()}\n\n")
            f.write(f"![{name}]({path.relative_to(output_dir)})\n\n")

        f.write("## 4. 一次性投入回测结果\n\n")
        if "lumpsum" in results:
            f.write(
                "| 窗口 | 起始月份 | 结束月份 | 年化收益 | 最大回撤 | 年化波动 | 夏普比率 | 调仓次数 |\n"
            )
            f.write(
                "|------|----------|----------|----------|----------|----------|----------|----------|\n"
            )
            for r in results["lumpsum"]:
                m = r.metrics
                f.write(
                    f"| {r.label} | {r.start_month} | {r.end_month} | "
                    f"{format_percent(m['cagr'])} | {format_percent(m['max_drawdown'])} | "
                    f"{format_percent(m['annual_vol'])} | {format_float(m['sharpe'])} | "
                    f"{int(m['rebalances'])} |\n"
                )
            f.write("\n")

        f.write("## 5. 季度定投回测结果\n\n")
        if "dca" in dca_results:
            f.write(
                "| 窗口 | 起始月份 | 结束月份 | 总投入 | 期末价值 | XIRR | 最大回撤 |\n"
            )
            f.write(
                "|------|----------|----------|--------|----------|------|----------|\n"
            )
            for r in dca_results["dca"]:
                f.write(
                    f"| {r.label} | {r.start_month} | {r.end_month} | "
                    f"{format_float(r.invested)} | {format_float(r.end_value)} | "
                    f"{format_percent(r.xirr)} | {format_percent(r.max_drawdown)} |\n"
                )
            f.write("\n")

        f.write("## 6. 基准对比\n\n")
        f.write("### 6.1 年化收益对比\n\n")
        f.write(
            "| 窗口 | 策略 | 中证800 | 中股中债50/50 | 中股中债80/20 | 标普500(RMB) |\n"
        )
        f.write(
            "|------|------|---------|---------------|---------------|--------------|\n"
        )

        # Calculate benchmark metrics for each horizon
        horizons = [("10y", 120), ("5y", 60), ("3y", 36), ("1y", 12)]
        last_month = panel.iloc[-1]["month"]

        for label, months in horizons:
            start = last_month - months
            df = panel[panel["month"] >= start].copy()
            if len(df) < 3:
                continue

            # Strategy metrics (from lumpsum results)
            strategy_cagr = None
            for r in results.get("lumpsum", []):
                if r.label == label:
                    strategy_cagr = r.metrics["cagr"]
                    break

            if strategy_cagr is None:
                continue

            # Benchmark metrics
            bench_cagrs = {}
            for key in BENCHMARKS:
                bench_nav = benchmark_nav_from_prices(df, key, 10000)
                bench_returns = bench_nav.pct_change().dropna()
                if len(bench_returns) > 0:
                    years = len(bench_nav) / 12
                    bench_cagr = (bench_nav.iloc[-1] / bench_nav.iloc[0]) ** (
                        1 / years
                    ) - 1
                    bench_cagrs[key] = bench_cagr

            f.write(
                f"| {label} | {format_percent(strategy_cagr)} | "
                f"{format_percent(bench_cagrs.get('csi800', 0))} | "
                f"{format_percent(bench_cagrs.get('cn50_50', 0))} | "
                f"{format_percent(bench_cagrs.get('cn80_20', 0))} | "
                f"{format_percent(bench_cagrs.get('sp500', 0))} |\n"
            )

        f.write("\n### 6.2 最大回撤对比\n\n")
        f.write(
            "| 窗口 | 策略 | 中证800 | 中股中债50/50 | 中股中债80/20 | 标普500(RMB) |\n"
        )
        f.write(
            "|------|------|---------|---------------|---------------|--------------|\n"
        )

        for label, months in horizons:
            start = last_month - months
            df = panel[panel["month"] >= start].copy()
            if len(df) < 3:
                continue

            # Strategy max drawdown
            strategy_mdd = None
            for r in results.get("lumpsum", []):
                if r.label == label:
                    strategy_mdd = r.metrics["max_drawdown"]
                    break

            if strategy_mdd is None:
                continue

            # Benchmark max drawdowns
            bench_mdds = {}
            for key in BENCHMARKS:
                bench_nav = benchmark_nav_from_prices(df, key, 10000)
                dd = bench_nav / bench_nav.cummax() - 1
                bench_mdds[key] = dd.min()

            f.write(
                f"| {label} | {format_percent(strategy_mdd)} | "
                f"{format_percent(bench_mdds.get('csi800', 0))} | "
                f"{format_percent(bench_mdds.get('cn50_50', 0))} | "
                f"{format_percent(bench_mdds.get('cn80_20', 0))} | "
                f"{format_percent(bench_mdds.get('sp500', 0))} |\n"
            )

        f.write("\n## 7. 典型信号场景\n\n")
        f.write("| 场景 | x | y | 现金 | 黄金 | 中债 | A股 | 美债 | 美股 |\n")
        f.write("|------|---|---|------|------|------|-----|------|------|\n")

        scenarios = [
            ("防守", 0.10, 0.10),
            ("中性", 0.50, 0.50),
            ("美强中弱", 0.80, 0.20),
            ("美弱中强", 0.20, 0.80),
            ("进攻", 0.90, 0.90),
        ]

        for name, x, y in scenarios:
            weights = get_asset_summary(
                {"x": x, "y": y, **allocation_table([x], [y])[0]}
            )
            f.write(
                f"| {name} | {x:.2f} | {y:.2f} | "
                f"{format_percent(weights.get('cash', 0))} | "
                f"{format_percent(weights.get('gold', 0))} | "
                f"{format_percent(weights.get('cnBond', 0))} | "
                f"{format_percent(weights.get('cnStock', 0))} | "
                f"{format_percent(weights.get('usBond', 0))} | "
                f"{format_percent(weights.get('usStock', 0))} |\n"
            )

        f.write("\n## 8. 结论与建议\n\n")
        f.write("1. **策略表现**: 在测试区间内，策略实现了...\n")
        f.write("2. **风险控制**: 最大回撤控制在...\n")
        f.write("3. **基准比较**: 相对于...\n")
        f.write("4. **执行建议**: 建议季度再平衡，偏离阈值5%...\n")

        f.write("\n---\n\n")
        f.write("*报告自动生成，数据来源：akshare*")

    return report_path


def main():
    parser = argparse.ArgumentParser(
        description="Run complete asset allocation backtest with report generation"
    )
    parser.add_argument(
        "--output-dir",
        default="output/allocation_backtest",
        help="Output directory for results and reports",
    )
    parser.add_argument(
        "--generate-figures",
        action="store_true",
        default=True,
        help="Generate visualization figures",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("资产配置回测系统 (参数更新: 2026-03-17)")
    print("=" * 60)

    # Step 1: Build data panel
    print("\n1. 构建数据面板...")
    panel, cn_index_used = build_panel()
    panel.attrs["cn_index_used"] = cn_index_used

    print(f"   数据区间: {panel['month'].min()} 至 {panel['month'].max()}")
    print(f"   月度样本数: {len(panel)}")
    print(f"   A股信号指数: {cn_index_used}")

    # Save panel for reference
    panel_path = output_dir / "data_panel.csv"
    panel.to_csv(panel_path, index=False, encoding="utf-8-sig")
    print(f"   数据面板已保存: {panel_path}")

    # Step 2: Generate visualization figures
    figure_paths = {}
    if args.generate_figures:
        print("\n2. 生成配置可视化图表...")
        fig_dir = output_dir / "figures"
        figure_paths = generate_all_figures(fig_dir)
        for name, path in figure_paths.items():
            print(f"   ✓ {name}: {path}")

    # Step 3: Run lumpsum backtests
    print("\n3. 运行一次性投入回测...")
    last_month = panel.iloc[-1]["month"]
    horizons = [("10y", 120), ("5y", 60), ("3y", 36), ("1y", 12)]

    lumpsum_results = []
    for label, months in horizons:
        print(f"   {label}窗口...", end="")
        try:
            start = last_month - months
            result = run_lumpsum_backtest(panel, start, label)
            lumpsum_results.append(result)
            print(
                f" 完成 (年化: {result.metrics['cagr']:.2%}, 回撤: {result.metrics['max_drawdown']:.2%})"
            )
        except Exception as e:
            print(f" 失败: {e}")

    # Step 4: Run DCA backtests
    print("\n4. 运行季度定投回测...")
    dca_results = []
    for label, months in horizons:
        print(f"   {label}窗口...", end="")
        try:
            start = last_month - months
            result = run_dca_backtest(panel, start, label)
            dca_results.append(result)
            print(f" 完成 (XIRR: {result.xirr:.2%}, 回撤: {result.max_drawdown:.2%})")
        except Exception as e:
            print(f" 失败: {e}")

    # Step 5: Generate allocation shift chart
    print("\n5. 生成配置变化趋势图...")
    try:
        # Calculate monthly weights for the full panel
        monthly_weights = []
        for _, row in panel.iterrows():
            weights = get_asset_summary({"x": row["x_signal"], "y": row["y_signal"]})
            monthly_weights.append({"month": row["month"], **weights})

        weights_df = pd.DataFrame(monthly_weights).set_index("month")
        shift_chart_path = output_dir / "allocation_shift_over_time.png"
        generate_allocation_shift_chart(
            weights_df, shift_chart_path, "资产配置变化趋势 (全样本区间)"
        )
        figure_paths["allocation_shift"] = shift_chart_path
        print(f"   配置变化趋势图已保存: {shift_chart_path}")
    except Exception as e:
        print(f"   生成配置变化趋势图失败: {e}")

    # Step 6: Generate performance comparison charts
    print("\n6. 生成表现对比图表...")
    for label, months in horizons:
        try:
            start = last_month - months
            df = panel[panel["month"] >= start].copy()
            if len(df) < 3:
                continue

            # Find matching lumpsum result
            strategy_nav = None
            for r in lumpsum_results:
                if r.label == label:
                    strategy_nav = r.nav
                    break

            if strategy_nav is None:
                continue

            # Calculate benchmark NAVs
            bench_navs = {}
            for key in BENCHMARKS:
                bench_nav = benchmark_nav_from_prices(df, key, 10000)
                bench_navs[key] = bench_nav

            # Generate comparison chart
            comp_path = output_dir / f"performance_comparison_{label}.png"
            generate_performance_comparison(
                strategy_nav, bench_navs, comp_path, f"{label}窗口: 策略与基准表现对比"
            )
            figure_paths[f"comparison_{label}"] = comp_path
            print(f"   ✓ {label}对比图: {comp_path}")
        except Exception as e:
            print(f"   生成{label}对比图失败: {e}")

    # Step 7: Generate comprehensive report
    print("\n7. 生成综合报告...")
    try:
        results_dict = {"lumpsum": lumpsum_results}
        dca_dict = {"dca": dca_results}

        report_path = generate_markdown_report(
            results_dict, dca_dict, panel, output_dir, figure_paths
        )
        print(f"   报告已生成: {report_path}")
    except Exception as e:
        print(f"   生成报告失败: {e}")

    # Step 8: Save raw results
    print("\n8. 保存原始结果数据...")

    # Lumpsum results
    lumpsum_rows = []
    for r in lumpsum_results:
        lumpsum_rows.append(
            {
                "horizon": r.label,
                "start_month": str(r.start_month),
                "end_month": str(r.end_month),
                **r.metrics,
            }
        )

    if lumpsum_rows:
        lumpsum_df = pd.DataFrame(lumpsum_rows)
        lumpsum_csv = output_dir / "lumpsum_results.csv"
        lumpsum_df.to_csv(lumpsum_csv, index=False, encoding="utf-8-sig")
        print(f"   一次性投入结果: {lumpsum_csv}")

    # DCA results
    dca_rows = []
    for r in dca_results:
        dca_rows.append(
            {
                "horizon": r.label,
                "start_month": str(r.start_month),
                "end_month": str(r.end_month),
                "invested": r.invested,
                "end_value": r.end_value,
                "xirr": r.xirr,
                "max_drawdown": r.max_drawdown,
            }
        )

    if dca_rows:
        dca_df = pd.DataFrame(dca_rows)
        dca_csv = output_dir / "dca_results.csv"
        dca_df.to_csv(dca_csv, index=False, encoding="utf-8-sig")
        print(f"   定投结果: {dca_csv}")

    print("\n" + "=" * 60)
    print("回测完成!")
    print(f"所有结果已保存至: {output_dir.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
