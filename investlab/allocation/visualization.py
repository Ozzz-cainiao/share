#!/usr/bin/env python3
"""Visualization tools for asset allocation with updated parameters.

Updated parameters (2026-03-17):
    cash = 2% (fixed)
    gold = 8% (fixed)
    usBond = 8% (fixed)
    usStock = 20% + 30% * xUsPremium (range 20%-50%)
    cnStock = 20% + remaining * yCnSignal (minimum 20%)
    cnBond = remaining * (1 - yCnSignal)

Includes:
1. 3D stacked bar chart
2. Weight heatmaps for each asset
3. Signal slice plots
4. Typical scenario table
5. Allocation shift over time
6. Performance comparison charts
"""

from pathlib import Path
from typing import Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch, FancyBboxPatch

from investlab.allocation.calculator import (
    target_weights,
    ASSET_COLORS,
    ASSET_LABELS,
    ASSET_ORDER,
    CASH_RATIO,
    GOLD_RATIO,
    US_BOND_RATIO,
    BASE_US_STOCK,
    US_STOCK_RANGE,
    BASE_CN_STOCK,
)

plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "Arial Unicode MS",
]
plt.rcParams["axes.unicode_minus"] = False

# Layer definitions for stacking (order from bottom to top)
LAYERS = [
    ("cash", "现金", ASSET_COLORS["cash"]),
    ("gold", "黄金", ASSET_COLORS["gold"]),
    ("cnBond", "中债", ASSET_COLORS["cnBond"]),
    ("usBond", "美债", ASSET_COLORS["usBond"]),
    ("cnStock", "A股", ASSET_COLORS["cnStock"]),
    ("usStock", "美股", ASSET_COLORS["usStock"]),
]


def generate_3d_stacked_chart(
    out_path: Path,
    x_resolution: int = 11,
    y_resolution: int = 11,
) -> None:
    """Generate 3D stacked bar chart showing allocation across signal space."""
    x_vals = np.linspace(0.0, 1.0, x_resolution)
    y_vals = np.linspace(0.0, 1.0, y_resolution)

    fig = plt.figure(figsize=(13, 9))
    ax = fig.add_subplot(111, projection="3d")

    dx = 0.08
    dy = 0.08

    for x in x_vals:
        for y in y_vals:
            weights = target_weights(float(x), float(y))
            z0 = 0.0
            for key, _, color in LAYERS:
                dz = float(weights[key])
                ax.bar3d(
                    x - dx / 2,
                    y - dy / 2,
                    z0,
                    dx,
                    dy,
                    dz,
                    color=color,
                    alpha=0.95,
                    shade=True,
                    zsort="average",
                )
                z0 += dz

    ax.set_title("三维堆叠资产配置图（cash=2%, gold=8%, usBond=8%）", pad=16)
    ax.set_xlabel("美股风险信号 xUsPremium", labelpad=12)
    ax.set_ylabel("A股风险信号 yCnSignal", labelpad=12)
    ax.set_zlabel("资产权重", labelpad=12)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_zlim(0, 1)
    ax.view_init(elev=26, azim=-132)

    legend_handles = [
        Patch(facecolor=color, edgecolor="none", label=cn_name)
        for _, cn_name, color in LAYERS
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper left",
        bbox_to_anchor=(0.02, 0.98),
        frameon=True,
        title="资产图例",
    )

    plt.tight_layout()
    plt.savefig(out_path, dpi=220)
    plt.close(fig)


def generate_weight_heatmaps(out_path: Path, resolution: int = 101) -> None:
    """Generate heatmaps showing asset weights across signal space."""
    x_vals = np.linspace(0.0, 1.0, resolution)
    y_vals = np.linspace(0.0, 1.0, resolution)
    X, Y = np.meshgrid(x_vals, y_vals)

    fields = {
        "usStock": np.zeros_like(X),
        "cnStock": np.zeros_like(X),
        "usBond": np.zeros_like(X),
        "cnBond": np.zeros_like(X),
        "equity": np.zeros_like(X),
        "bond": np.zeros_like(X),
    }

    for i in range(X.shape[0]):
        for j in range(X.shape[1]):
            w = target_weights(float(X[i, j]), float(Y[i, j]))
            for k in ("usStock", "cnStock", "usBond", "cnBond"):
                fields[k][i, j] = w[k]
            fields["equity"][i, j] = w["usStock"] + w["cnStock"]
            fields["bond"][i, j] = w["usBond"] + w["cnBond"]

    fig, axes = plt.subplots(2, 3, figsize=(16, 9), constrained_layout=True)
    plot_items = [
        ("usStock", "美股权重"),
        ("cnStock", "A股权重"),
        ("usBond", "美债权重（固定8%）"),
        ("cnBond", "中债权重"),
        ("equity", "总股仓"),
        ("bond", "总债仓"),
    ]

    for ax, (key, title) in zip(axes.flat, plot_items):
        im = ax.contourf(X, Y, fields[key], levels=31, cmap="YlGnBu")
        ax.set_title(title)
        ax.set_xlabel("美股信号 x")
        ax.set_ylabel("A股信号 y")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label("权重")

    plt.savefig(out_path, dpi=220)
    plt.close(fig)


def generate_signal_slices(out_path: Path, resolution: int = 101) -> None:
    """Generate slice plots showing weight changes along signal dimensions."""
    x_vals = np.linspace(0.0, 1.0, resolution)
    y_vals = np.linspace(0.0, 1.0, resolution)

    fig, axes = plt.subplots(2, 2, figsize=(14, 9), constrained_layout=True)

    # Fixed y, varying x
    for y in (0.2, 0.5, 0.8):
        us, cn = [], []
        for x in x_vals:
            w = target_weights(float(x), float(y))
            us.append(w["usStock"])
            cn.append(w["cnStock"])
        axes[0, 0].plot(x_vals, us, label=f"y={y}")
        axes[0, 1].plot(x_vals, cn, label=f"y={y}")

    # Fixed x, varying y
    for x in (0.2, 0.5, 0.8):
        cn_s, cn_b = [], []
        for y in y_vals:
            w = target_weights(float(x), float(y))
            cn_s.append(w["cnStock"])
            cn_b.append(w["cnBond"])
        axes[1, 0].plot(y_vals, cn_s, label=f"x={x}")
        axes[1, 1].plot(y_vals, cn_b, label=f"x={x}")

    axes[0, 0].set_title("固定 y，看美股随 x 变化")
    axes[0, 1].set_title("固定 y，看A股随 x 变化")
    axes[1, 0].set_title("固定 x，看A股随 y 变化")
    axes[1, 1].set_title("固定 x，看中债随 y 变化")

    for ax in axes.flat:
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.grid(alpha=0.25)
        ax.legend()

    axes[0, 0].set_xlabel("x")
    axes[0, 0].set_ylabel("权重")
    axes[0, 1].set_xlabel("x")
    axes[0, 1].set_ylabel("权重")
    axes[1, 0].set_xlabel("y")
    axes[1, 0].set_ylabel("权重")
    axes[1, 1].set_xlabel("y")
    axes[1, 1].set_ylabel("权重")

    plt.savefig(out_path, dpi=220)
    plt.close(fig)


def generate_typical_scenarios(out_path: Path) -> None:
    """Generate table of typical allocation scenarios."""
    scenarios = [
        ("防守", 0.10, 0.10),
        ("中性", 0.50, 0.50),
        ("美强中弱", 0.80, 0.20),
        ("美弱中强", 0.20, 0.80),
        ("进攻", 0.90, 0.90),
    ]

    headers = ["场景", "x", "y", "现金", "黄金", "中债", "A股", "美债", "美股"]
    table_data = []
    for name, x, y in scenarios:
        w = target_weights(x, y)
        table_data.append(
            [
                name,
                f"{x:.2f}",
                f"{y:.2f}",
                f"{w['cash']:.1%}",
                f"{w['gold']:.1%}",
                f"{w['cnBond']:.1%}",
                f"{w['cnStock']:.1%}",
                f"{w['usBond']:.1%}",
                f"{w['usStock']:.1%}",
            ]
        )

    fig, ax = plt.subplots(figsize=(12, 3.8))
    ax.axis("off")
    tbl = ax.table(
        cellText=table_data, colLabels=headers, loc="center", cellLoc="center"
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(11)
    tbl.scale(1, 1.5)
    ax.set_title("典型场景资产比例（cash=2%, gold=8%, usBond=8%）", pad=14)

    plt.tight_layout()
    plt.savefig(out_path, dpi=220)
    plt.close(fig)


def generate_allocation_shift_chart(
    weights_df: pd.DataFrame,
    out_path: Path,
    title: str = "资产配置变化趋势",
) -> None:
    """Generate stacked area chart showing allocation shifts over time."""
    fig, ax = plt.subplots(figsize=(14, 7))

    # Reorder columns according to ASSET_ORDER
    ordered_cols = [col for col in ASSET_ORDER if col in weights_df.columns]
    weights_ordered = weights_df[ordered_cols]

    # Convert to percentages
    weights_pct = weights_ordered * 100

    # Stacked area plot
    ax.stackplot(
        weights_df.index,
        *[weights_pct[col] for col in ordered_cols],
        labels=[ASSET_LABELS[col] for col in ordered_cols],
        colors=[ASSET_COLORS[col] for col in ordered_cols],
        alpha=0.85,
    )

    ax.set_title(title, fontsize=14)
    ax.set_xlabel("日期")
    ax.set_ylabel("配置比例 (%)")
    ax.grid(alpha=0.25)
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), borderaxespad=0)
    ax.set_ylim(0, 100)

    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close(fig)


def generate_performance_comparison(
    strategy_nav: pd.Series,
    benchmark_navs: Dict[str, pd.Series],
    out_path: Path,
    title: str = "策略与基准表现对比",
) -> None:
    """Generate performance comparison chart with drawdown."""
    idx = strategy_nav.index.astype(str)
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )

    # Normalize to starting value
    ax1.plot(
        idx,
        strategy_nav / strategy_nav.iloc[0],
        color="#0B4F9C",
        linewidth=2.2,
        label="策略",
    )

    benchmark_colors = ["#2CA02C", "#9467BD", "#8C564B", "#E377C2"]
    for (key, nav), color in zip(benchmark_navs.items(), benchmark_colors):
        ax1.plot(idx, nav / nav.iloc[0], linewidth=1.5, label=key, color=color)

    ax1.set_title(title)
    ax1.set_ylabel("净值（起点=1.0）")
    ax1.grid(alpha=0.25)
    ax1.legend(ncol=3, fontsize=9)

    # Drawdown
    dd = strategy_nav / strategy_nav.cummax() - 1
    ax2.plot(idx, dd * 100, color="#B24D4D", linewidth=1.5, label="策略回撤")
    ax2.set_ylabel("回撤 (%)")
    ax2.grid(alpha=0.25)
    ax2.legend()

    step = max(1, len(idx) // 12)
    xt = np.arange(0, len(idx), step)
    ax2.set_xticks(xt)
    ax2.set_xticklabels([idx[i] for i in xt], rotation=45, ha="right")

    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close(fig)


def generate_rolling_7y_quarterly_rebalance_summary(
    results_df: pd.DataFrame, out_path: Path
) -> None:
    """Generate rolling 7-year quarterly rebalance summary chart.

    Args:
        results_df: DataFrame with columns:
            - start_month: period start
            - cagr: annualized return
            - max_drawdown: maximum drawdown
            - sharpe: sharpe ratio (optional)
            - rebalances: number of rebalances (optional)
        out_path: output file path
    """
    x = np.arange(len(results_df))
    labels = results_df["start_month"].astype(str).tolist()

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 9), sharex=True, gridspec_kw={"height_ratios": [2, 2]}
    )

    # CAGR plot
    ax1.plot(
        x,
        results_df["cagr"] * 100,
        marker="o",
        color="#2F6DB3",
        linewidth=1.8,
        label="7年年化收益",
    )
    ax1.axhline(
        results_df["cagr"].median() * 100,
        color="#888888",
        linestyle="--",
        linewidth=1.2,
        label="中位数",
    )
    ax1.set_ylabel("年化收益（%）")
    ax1.set_title("最近10年：按季度起点的7年滚动回测（季度再平衡）")
    ax1.grid(alpha=0.25)
    ax1.legend(loc="best")

    # Max drawdown plot
    ax2.bar(
        x,
        results_df["max_drawdown"] * 100,
        color="#D87070",
        alpha=0.85,
        label="最大回撤",
    )
    ax2.axhline(
        results_df["max_drawdown"].median() * 100,
        color="#888888",
        linestyle="--",
        linewidth=1.2,
        label="中位数",
    )
    ax2.set_ylabel("最大回撤（%）")
    ax2.set_xlabel("起投季度")
    ax2.grid(alpha=0.25)
    ax2.legend(loc="best")

    # X-axis ticks
    step = max(1, len(labels) // 14)
    ticks = np.arange(0, len(labels), step)
    ax2.set_xticks(ticks)
    ax2.set_xticklabels([labels[i] for i in ticks], rotation=45, ha="right")

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=180)
    plt.close(fig)


def generate_rolling_7y_quarterly_dca_10k_summary(
    results_df: pd.DataFrame, out_path: Path
) -> None:
    """Generate rolling 7-year quarterly DCA summary chart.

    Args:
        results_df: DataFrame with columns:
            - start_month: period start
            - xirr: internal rate of return
            - cagr_on_total_cost: annualized return on total cost
            - total_invested: total amount invested
            - end_value: ending portfolio value
            - max_drawdown: maximum drawdown
        out_path: output file path
    """
    x = np.arange(len(results_df))
    labels = results_df["start_month"].astype(str).tolist()

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(14, 9), sharex=True, gridspec_kw={"height_ratios": [2, 2]}
    )

    # Return metrics
    ax1.plot(
        x,
        results_df["xirr"] * 100,
        marker="o",
        color="#2F6DB3",
        linewidth=1.8,
        label="XIRR",
    )
    ax1.plot(
        x,
        results_df["cagr_on_total_cost"] * 100,
        marker="s",
        color="#579D5B",
        linewidth=1.6,
        label="按总投入折算年化",
    )
    ax1.axhline(
        results_df["xirr"].median() * 100,
        color="#666666",
        linestyle="--",
        linewidth=1.1,
        label="XIRR中位数",
    )
    ax1.set_ylabel("收益率（%）")
    ax1.set_title("季度定投1万元：7年窗口滚动结果")
    ax1.grid(alpha=0.25)
    ax1.legend(loc="best")

    # Investment amount and drawdown
    width = 0.38
    ax2.bar(
        x - width / 2,
        results_df["total_invested"] / 10000,
        width=width,
        color="#C9A14A",
        label="累计投入（万元）",
    )
    ax2.bar(
        x + width / 2,
        results_df["end_value"] / 10000,
        width=width,
        color="#4F84C4",
        label="期末资产（万元）",
    )
    ax2_t = ax2.twinx()
    ax2_t.plot(
        x,
        results_df["max_drawdown"] * 100,
        color="#B24D4D",
        marker="^",
        linewidth=1.4,
        label="最大回撤",
    )

    ax2.set_ylabel("金额（万元）")
    ax2_t.set_ylabel("最大回撤（%）")
    ax2.set_xlabel("起投季度")
    ax2.grid(alpha=0.2)

    # Combine legends
    h1, l1 = ax2.get_legend_handles_labels()
    h2, l2 = ax2_t.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, loc="best")

    # X-axis ticks
    step = max(1, len(labels) // 14)
    ticks = np.arange(0, len(labels), step)
    ax2.set_xticks(ticks)
    ax2.set_xticklabels([labels[i] for i in ticks], rotation=45, ha="right")

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=180)
    plt.close(fig)


def generate_allocation_backtest_chart(
    nav: pd.Series,
    drawdown: pd.Series,
    metrics: Dict[str, float],
    label: str,
    out_path: Path,
) -> None:
    """Generate allocation backtest chart (like allocation_backtest_3y.png).

    Args:
        nav: NAV series with datetime index
        drawdown: drawdown series (0 to -1)
        metrics: dictionary with metrics:
            - cagr: annualized return
            - total_return: total return
            - max_drawdown: maximum drawdown
            - annual_vol: annual volatility
            - rebalances: number of rebalances
        label: horizon label (e.g., "3y")
        out_path: output file path
    """
    idx = nav.index.astype(str)
    norm = nav / nav.iloc[0]

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(12, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )

    # NAV plot
    ax1.plot(idx, norm.values, color="#2F6DB3", linewidth=2.0, label="组合净值")
    ax1.set_ylabel("净值（起点=1.0）")
    ax1.grid(alpha=0.25)
    ax1.legend(loc="upper left")
    ax1.set_title(f"{label}回测（按月检查，偏离>5%调仓）")

    # Metrics text
    txt = (
        f"年化收益: {metrics['cagr']:.2%}  |  累计收益: {metrics['total_return']:.2%}  |  "
        f"最大回撤: {metrics['max_drawdown']:.2%}  |  年化波动: {metrics['annual_vol']:.2%}  |  "
        f"调仓次数: {int(metrics['rebalances'])}"
    )
    ax1.text(0.01, 0.03, txt, transform=ax1.transAxes, fontsize=10, va="bottom")

    # Drawdown plot
    ax2.fill_between(idx, np.asarray(drawdown) * 100, 0, color="#D87070", alpha=0.35)
    ax2.plot(idx, np.asarray(drawdown) * 100, color="#B24D4D", linewidth=1.5)
    ax2.set_ylabel("回撤（%）")
    ax2.grid(alpha=0.25)

    # X-axis ticks
    step = max(1, len(idx) // 12)
    xt = np.arange(0, len(idx), step)
    ax2.set_xticks(xt)
    ax2.set_xticklabels([idx[i] for i in xt], rotation=45, ha="right")

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=180)
    plt.close(fig)


def generate_allocation_shift_10y_quarterly_stack(
    weights_df: pd.DataFrame,
    out_path: Path,
    title: str = "过去10年目标资产权重变化（按季度）",
) -> None:
    """Generate 10-year quarterly stacked allocation shift chart.

    Args:
        weights_df: DataFrame with datetime index and columns:
            - cash, gold, cnBond, cnStock, usBond, usStock
        out_path: output file path
        title: chart title
    """
    # Filter to quarter-end months (Mar, Jun, Sep, Dec)
    # Handle different index types (PeriodIndex or DatetimeIndex)
    import pandas as pd

    if isinstance(weights_df.index, pd.PeriodIndex):
        # Convert PeriodIndex to DatetimeIndex for month extraction
        dt_index = weights_df.index.to_timestamp()
        month_mask = dt_index.month.isin([3, 6, 9, 12])  # type: ignore
    elif isinstance(weights_df.index, pd.DatetimeIndex):
        month_mask = weights_df.index.month.isin([3, 6, 9, 12])  # type: ignore
    else:
        # Try to access month attribute as fallback
        month_mask = weights_df.index.month.isin([3, 6, 9, 12])  # type: ignore

    qdf = weights_df[month_mask].copy()
    if qdf.empty:
        qdf = weights_df  # fallback to all months

    idx = [str(i) for i in qdf.index]
    cols = ["cash", "gold", "cnBond", "cnStock", "usBond", "usStock"]
    labels = ["现金", "黄金", "中债", "中股", "美债", "美股"]
    colors = ["#6FAF9F", "#E6D58A", "#AEB6D6", "#5E93CF", "#DFA0AC", "#D77A6C"]

    fig, ax = plt.subplots(figsize=(14, 7))
    # Prepare data for stackplot
    stack_data = [np.asarray(qdf[c]) for c in cols]
    ax.stackplot(idx, stack_data, labels=labels, colors=colors, alpha=0.9)
    ax.set_title(title)
    ax.set_ylabel("权重")
    ax.set_ylim(0, 1)
    ax.grid(alpha=0.2)
    ax.legend(loc="upper left", ncol=3)

    step = max(1, len(idx) // 18)
    xt = np.arange(0, len(idx), step)
    ax.set_xticks(xt)
    tick_labels = [idx[i] for i in xt]
    ax.set_xticklabels(tick_labels, rotation=45, ha="right")

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=180)
    plt.close(fig)


def generate_all_figures(output_dir: Path) -> Dict[str, Path]:
    """Generate all standard figures for documentation."""
    output_dir.mkdir(parents=True, exist_ok=True)

    figure_paths = {}

    # 3D stacked chart
    fig1 = output_dir / "fig_3d_stacked.png"
    generate_3d_stacked_chart(fig1)
    figure_paths["3d_stacked"] = fig1

    # Heatmaps
    fig2 = output_dir / "fig_weight_heatmaps.png"
    generate_weight_heatmaps(fig2)
    figure_paths["weight_heatmaps"] = fig2

    # Signal slices
    fig3 = output_dir / "fig_signal_slices.png"
    generate_signal_slices(fig3)
    figure_paths["signal_slices"] = fig3

    # Typical scenarios
    fig4 = output_dir / "fig_typical_scenarios.png"
    generate_typical_scenarios(fig4)
    figure_paths["typical_scenarios"] = fig4

    return figure_paths


if __name__ == "__main__":
    # Test generation
    out_dir = Path("output/figures")
    paths = generate_all_figures(out_dir)
    print("Generated figures:")
    for name, path in paths.items():
        print(f"  {name}: {path}")
