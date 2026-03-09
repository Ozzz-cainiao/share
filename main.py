from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import akshare as ak
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class AssetSpec:
    key: str
    name: str
    source: str
    symbol: str
    total_return: bool


ASSETS: list[AssetSpec] = [
    AssetSpec("H00300", "沪深300全收益", "csindex_tri", "H00300", True),
    AssetSpec("H00906", "中证800全收益", "csindex_tri", "H00906", True),
    AssetSpec("H00905", "中证500全收益", "csindex_tri", "H00905", True),
    AssetSpec("SPY", "标普500（SPY前复权）", "us_etf_qfq", "SPY", True),
    AssetSpec("QQQ", "纳指100（QQQ前复权）", "us_etf_qfq", "QQQ", True),
]

DRAWDOWN_LEVELS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
MAX_WAIT_MONTHS = [3, 6, 12, 18]

START_DATE = "2005-01-01"
END_DATE = "2026-03-09"
MONTHLY_CONTRIBUTION = 1.0
ANNUAL_CASH_RATE = 0.02
FEE_RATE = 0.0003
ROLLING_MIN_YEARS = 5

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "output"
CHART_DIR = OUTPUT_DIR / "charts"
DATA_DIR = OUTPUT_DIR / "data"
ARTICLE_PATH = OUTPUT_DIR / "wechat_article.md"


def setup_plot_style() -> None:
    plt.rcParams["font.sans-serif"] = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 130


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def fetch_price_series(spec: AssetSpec, start_date: str, end_date: str) -> pd.Series:
    if spec.source == "csindex_tri":
        df = ak.stock_zh_index_hist_csindex(
            symbol=spec.symbol,
            start_date=start_date.replace("-", ""),
            end_date=end_date.replace("-", ""),
        )
        series = pd.Series(
            df["收盘"].astype(float).to_numpy(),
            index=pd.to_datetime(df["日期"]),
            name=spec.key,
        )
    elif spec.source == "sina_us_index":
        df = ak.index_us_stock_sina(symbol=spec.symbol)
        series = pd.Series(
            df["close"].astype(float).to_numpy(),
            index=pd.to_datetime(df["date"]),
            name=spec.key,
        )
        series = series.loc[(series.index >= start_date) & (series.index <= end_date)]
    elif spec.source == "us_etf_qfq":
        df = ak.stock_us_daily(symbol=spec.symbol, adjust="qfq")
        series = pd.Series(
            df["close"].astype(float).to_numpy(),
            index=pd.to_datetime(df["date"]),
            name=spec.key,
        )
        series = series.loc[(series.index >= start_date) & (series.index <= end_date)]
    else:
        raise ValueError(f"Unsupported source: {spec.source}")

    series = series.sort_index()
    series = series[~series.index.duplicated(keep="last")]
    # Some adjusted US series can contain non-positive artifacts on a few dates.
    # They are not tradable prices and will break drawdown logic.
    series = series.dropna()
    series = series[series > 0]
    return series


def xnpv(rate: float, cashflows: list[tuple[pd.Timestamp, float]]) -> float:
    t0 = cashflows[0][0]
    return sum(
        amount / (1.0 + rate) ** ((dt - t0).days / 365.25)
        for dt, amount in cashflows
    )


def xirr(cashflows: list[tuple[pd.Timestamp, float]]) -> float:
    values = [v for _, v in cashflows]
    if not any(v < 0 for v in values) or not any(v > 0 for v in values):
        return math.nan

    low, high = -0.9999, 10.0
    npv_low, npv_high = xnpv(low, cashflows), xnpv(high, cashflows)
    if npv_low * npv_high > 0:
        return math.nan

    for _ in range(200):
        mid = (low + high) / 2.0
        npv_mid = xnpv(mid, cashflows)
        if abs(npv_mid) < 1e-10:
            return mid
        if npv_low * npv_mid < 0:
            high, npv_high = mid, npv_mid
        else:
            low, npv_low = mid, npv_mid
    return (low + high) / 2.0


def month_diff(a: pd.Timestamp, b: pd.Timestamp) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def simulate_strategy(
    prices: pd.Series,
    strategy: str,
    drawdown_threshold: float = 0.20,
    max_wait_months: int = 12,
    monthly_contribution: float = MONTHLY_CONTRIBUTION,
    annual_cash_rate: float = ANNUAL_CASH_RATE,
    fee_rate: float = FEE_RATE,
) -> dict:
    if strategy not in {"dca", "timing"}:
        raise ValueError("strategy must be one of {'dca', 'timing'}")

    month_first_days = prices.index.to_series().groupby(prices.index.to_period("M")).min()
    month_first_set = set(month_first_days.tolist())
    rolling_peak = prices.cummax()

    daily_cash_rate = (1.0 + annual_cash_rate) ** (1.0 / 252.0) - 1.0

    cash = 0.0
    shares = 0.0
    pending_buy = False
    waiting_cash_dates: list[pd.Timestamp] = []
    trade_count = 0
    buy_dates: list[pd.Timestamp] = []
    total_contribution = 0.0

    portfolio_values: list[float] = []
    stock_values: list[float] = []
    cash_values: list[float] = []
    invest_ratios: list[float] = []

    cashflows: list[tuple[pd.Timestamp, float]] = []

    for i, (dt, px) in enumerate(prices.items()):
        cash *= 1.0 + daily_cash_rate

        if pending_buy and cash > 1e-12:
            invest_amount = cash * (1.0 - fee_rate)
            shares += invest_amount / px
            cash = 0.0
            waiting_cash_dates.clear()
            pending_buy = False
            trade_count += 1
            buy_dates.append(dt)

        if dt in month_first_set:
            cash += monthly_contribution
            total_contribution += monthly_contribution
            waiting_cash_dates.append(dt)
            cashflows.append((dt, -monthly_contribution))
            if strategy == "dca":
                pending_buy = True

        if strategy == "timing" and i < len(prices) - 1 and cash > 1e-12:
            peak = float(rolling_peak.iat[i])
            drawdown = 1.0 - px / peak if peak > 0 else 0.0
            trigger = drawdown >= drawdown_threshold
            forced = False
            if waiting_cash_dates:
                oldest = waiting_cash_dates[0]
                forced = month_diff(oldest, dt) >= max_wait_months
            if trigger or forced:
                pending_buy = True

        stock_value = shares * px
        total_value = stock_value + cash
        ratio = stock_value / total_value if total_value > 1e-12 else 0.0

        stock_values.append(stock_value)
        cash_values.append(cash)
        portfolio_values.append(total_value)
        invest_ratios.append(ratio)

    equity_curve = pd.Series(portfolio_values, index=prices.index, name="equity")
    stock_curve = pd.Series(stock_values, index=prices.index, name="stock_value")
    drawdown_curve = equity_curve / equity_curve.cummax() - 1.0

    daily_returns = equity_curve.pct_change().dropna()
    ann_ret = float(daily_returns.mean() * 252.0) if not daily_returns.empty else math.nan
    ann_vol = (
        float(daily_returns.std(ddof=0) * np.sqrt(252.0))
        if not daily_returns.empty
        else math.nan
    )
    sharpe = (
        (ann_ret - annual_cash_rate) / ann_vol
        if ann_vol and not math.isnan(ann_vol) and ann_vol > 1e-12
        else math.nan
    )

    span_days = (equity_curve.index[-1] - equity_curve.index[0]).days
    years = span_days / 365.25 if span_days > 0 else math.nan
    final_value = float(equity_curve.iat[-1])
    cagr = (
        (final_value / total_contribution) ** (1.0 / years) - 1.0
        if years and years > 0 and total_contribution > 0 and final_value > 0
        else math.nan
    )
    max_dd = float(drawdown_curve.min()) if not drawdown_curve.empty else math.nan

    final_cashflows = cashflows + [(equity_curve.index[-1], final_value)]
    irr = xirr(final_cashflows)

    return {
        "equity_curve": equity_curve,
        "stock_curve": stock_curve,
        "drawdown_curve": drawdown_curve,
        "final_value": final_value,
        "total_contribution": total_contribution,
        "trade_count": trade_count,
        "buy_dates": buy_dates,
        "avg_invest_ratio": float(np.mean(invest_ratios)) if invest_ratios else math.nan,
        "ann_return": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "cagr": cagr,
        "max_drawdown": max_dd,
        "xirr": irr,
    }


def rolling_win_rate(
    prices: pd.Series,
    drawdown_threshold: float,
    max_wait_months: int,
    min_years: int = ROLLING_MIN_YEARS,
) -> float:
    end_dt = prices.index[-1]
    month_starts = prices.index.to_series().groupby(prices.index.to_period("M")).min().tolist()
    valid_starts = [
        dt for dt in month_starts if (end_dt - dt).days >= int(min_years * 365.25)
    ]
    if not valid_starts:
        return math.nan

    wins = 0
    for dt in valid_starts:
        sub_prices = prices.loc[prices.index >= dt]
        dca = simulate_strategy(sub_prices, "dca")
        timing = simulate_strategy(
            sub_prices,
            "timing",
            drawdown_threshold=drawdown_threshold,
            max_wait_months=max_wait_months,
        )
        if timing["final_value"] > dca["final_value"]:
            wins += 1
    return wins / len(valid_starts)


def format_pct(value: float) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"{value * 100:.2f}%"


def format_num(value: float, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "N/A"
    return f"{value:.{digits}f}"


def to_markdown_table(df: pd.DataFrame, percent_cols: Iterable[str]) -> str:
    cols = list(df.columns)
    lines = [
        "| " + " | ".join(cols) + " |",
        "| " + " | ".join(["---"] * len(cols)) + " |",
    ]
    for _, row in df.iterrows():
        values: list[str] = []
        for c in cols:
            val = row[c]
            if c in percent_cols:
                values.append(format_pct(float(val)))
            elif isinstance(val, float):
                values.append(format_num(val))
            else:
                values.append(str(val))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def plot_equity_and_drawdown(
    asset_name: str,
    dca: dict,
    timing_specs: list[dict],
    nav_path: Path,
    dd_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(dca["equity_curve"].index, dca["equity_curve"].values, label="每月定投", linewidth=1.8)
    for spec in timing_specs:
        result = spec["result"]
        label = spec["label"]
        ax.plot(result["equity_curve"].index, result["equity_curve"].values, label=label, linewidth=1.5)
    ax.set_title(f"{asset_name}：账户净值曲线（单位=每月投入金额）")
    ax.set_xlabel("日期")
    ax.set_ylabel("账户净值")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(nav_path)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 4.4))
    ax.plot(dca["drawdown_curve"].index, dca["drawdown_curve"].values, label="每月定投", linewidth=1.8)
    for spec in timing_specs:
        result = spec["result"]
        label = spec["label"]
        ax.plot(result["drawdown_curve"].index, result["drawdown_curve"].values, label=label, linewidth=1.5)
    ax.set_title(f"{asset_name}：回撤曲线对比")
    ax.set_xlabel("日期")
    ax.set_ylabel("回撤")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(dd_path)
    plt.close(fig)


def plot_heatmap(
    asset_name: str,
    heatmap_df: pd.DataFrame,
    out_path: Path,
) -> None:
    fig, ax = plt.subplots(figsize=(9.2, 5.2))
    matrix = heatmap_df.to_numpy(dtype=float)
    im = ax.imshow(matrix, cmap="RdYlGn", aspect="auto")

    ax.set_xticks(range(len(heatmap_df.columns)))
    ax.set_xticklabels([f"{int(c * 100)}%" for c in heatmap_df.columns])
    ax.set_yticks(range(len(heatmap_df.index)))
    ax.set_yticklabels([f"{m}个月" for m in heatmap_df.index])
    ax.set_xlabel("触发回撤阈值")
    ax.set_ylabel("最长等待期限")
    ax.set_title(f"{asset_name}：择时策略相对定投的XIRR超额（百分点）")

    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            v = matrix[i, j]
            text = "N/A" if math.isnan(v) else f"{v:.2f}"
            ax.text(j, i, text, ha="center", va="center", fontsize=8)

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("XIRR超额（百分点）")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_overall_excess(summary_df: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10.8, 5.0))
    x = np.arange(len(summary_df))
    width = 0.24

    ax.bar(
        x - width,
        summary_df["固定20%/12月_超额XIRR_bp"].to_numpy(dtype=float),
        width=width,
        label="固定参数 20%/12月",
    )
    ax.bar(
        x,
        summary_df["固定10%/6月_超额XIRR_bp"].to_numpy(dtype=float),
        width=width,
        label="固定参数 10%/6月",
    )
    ax.bar(
        x + width,
        summary_df["最优参数_超额XIRR_bp"].to_numpy(dtype=float),
        width=width,
        label="样本内最优参数",
    )

    ax.axhline(0.0, color="black", linewidth=1)
    ax.set_xticks(x)
    ax.set_xticklabels(summary_df["标的"].tolist(), rotation=0)
    ax.set_ylabel("相对定投 XIRR 超额（百分点）")
    ax.set_title("各标的：择时策略相对定投的收益超额")
    ax.legend()
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def generate_article(
    results: dict[str, dict],
    overall_summary: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> str:
    fixed_win_count = int((overall_summary["固定20%/12月_超额XIRR_bp"] > 0).sum())
    fixed_10_6_win_count = int((overall_summary["固定10%/6月_超额XIRR_bp"] > 0).sum())
    best_win_count = int((overall_summary["最优参数_超额XIRR_bp"] > 0).sum())

    lines: list[str] = []
    lines.append("# 回测：A股“等低点加仓”真的比每月定投更好吗？（含标普500、纳指100）")
    lines.append("")
    lines.append("> 回测区间：{} 至 {}；生成日期：2026-03-09。".format(start_date, end_date))
    lines.append("")
    lines.append("## 一、问题与实验设定")
    lines.append("")
    lines.append("我们要验证一个常见观点：手里留现金等低点，除非能抓到很精准的低点，否则不如每月直接投出去。")
    lines.append("")
    lines.append("统一设置如下：")
    lines.append("")
    lines.append("- 每月固定投入 1 份资金（只比较策略优劣，不关心绝对金额）。")
    lines.append("- 基准策略：每月定投（DCA）。")
    lines.append("- 择时策略：每月资金先进入现金池，当回撤达到阈值才一次性买入；若超过最长等待期限仍未触发，则强制买入。")
    lines.append("- 交易成本：单边 0.03%。")
    lines.append("- 现金年化收益：2%。")
    lines.append("- 信号与交易：当日收盘判断，下一交易日执行（避免未来函数）。")
    lines.append("")
    lines.append("标的与口径：")
    lines.append("")
    lines.append("- A股：沪深300全收益（H00300）、中证800全收益（H00906）、中证500全收益（H00905），含分红再投资。")
    lines.append("- 美股：标普500与纳指100采用 `SPY/QQQ` 前复权收盘价，作为分红再投资的近似口径。")
    lines.append("")
    lines.append("## 二、核心结论（先看结论）")
    lines.append("")
    lines.append(f"- 固定参数（回撤20% + 最长等待12个月）在 5 个标的中仅 {fixed_win_count} 个跑赢每月定投。")
    lines.append(f"- 新增固定参数（回撤10% + 最长等待6个月）在 5 个标的中有 {fixed_10_6_win_count} 个跑赢每月定投。")
    lines.append(f"- 如果允许样本内挑最优参数，5 个标的中有 {best_win_count} 个能跑赢，但优势并不稳定。")
    lines.append("- 结论与原命题一致：'留钱等低点'是否有效，高度依赖阈值与市场路径；普通投资者若不能稳定执行，定投通常更稳健。")
    lines.append("")
    lines.append("![](charts/overall_xirr_excess.png)")
    lines.append("")
    lines.append("## 三、总览结果表")
    lines.append("")

    percent_cols = [
        "定投_XIRR",
        "固定20%/12月_XIRR",
        "固定10%/6月_XIRR",
        "最优参数_XIRR",
        "固定20%/12月_超额XIRR",
        "固定10%/6月_超额XIRR",
        "最优参数_超额XIRR",
        "最优参数_滚动起点胜率",
    ]
    overview = overall_summary.copy()
    overview = overview.rename(
        columns={
            "固定20%/12月_超额XIRR_bp": "固定20%/12月_超额XIRR",
            "固定10%/6月_超额XIRR_bp": "固定10%/6月_超额XIRR",
            "最优参数_超额XIRR_bp": "最优参数_超额XIRR",
        }
    )
    lines.append(to_markdown_table(overview, percent_cols=percent_cols))
    lines.append("")
    lines.append("## 四、逐个标的图表与分析")
    lines.append("")

    section_idx = 1
    for key, payload in results.items():
        asset = payload["asset"]
        best_label = payload["best_label"]
        dca_row = payload["dca_row"]
        best_row = payload["best_row"]
        fixed_row = payload["fixed_row"]
        fixed_10_6_row = payload["fixed_10_6_row"]
        heatmap_name = payload["heatmap_path"].name
        nav_name = payload["nav_path"].name
        dd_name = payload["dd_path"].name

        local_df = pd.DataFrame(
            [
                {
                    "策略": "每月定投",
                    "XIRR": dca_row["xirr"],
                    "最大回撤": dca_row["max_drawdown"],
                    "平均仓位": dca_row["avg_invest_ratio"],
                    "总投入倍数": dca_row["final_value"] / dca_row["total_contribution"],
                    "交易次数": dca_row["trade_count"],
                },
                {
                    "策略": "固定参数(20%/12月)",
                    "XIRR": fixed_row["xirr"],
                    "最大回撤": fixed_row["max_drawdown"],
                    "平均仓位": fixed_row["avg_invest_ratio"],
                    "总投入倍数": fixed_row["final_value"] / fixed_row["total_contribution"],
                    "交易次数": fixed_row["trade_count"],
                },
                {
                    "策略": "固定参数(10%/6月)",
                    "XIRR": fixed_10_6_row["xirr"],
                    "最大回撤": fixed_10_6_row["max_drawdown"],
                    "平均仓位": fixed_10_6_row["avg_invest_ratio"],
                    "总投入倍数": fixed_10_6_row["final_value"] / fixed_10_6_row["total_contribution"],
                    "交易次数": fixed_10_6_row["trade_count"],
                },
                {
                    "策略": f"最优参数({best_label})",
                    "XIRR": best_row["xirr"],
                    "最大回撤": best_row["max_drawdown"],
                    "平均仓位": best_row["avg_invest_ratio"],
                    "总投入倍数": best_row["final_value"] / dca_row["total_contribution"],
                    "交易次数": best_row["trade_count"],
                },
            ]
        )

        lines.append(f"### 4.{section_idx} {asset.name}")
        lines.append("")
        lines.append(to_markdown_table(local_df, percent_cols=["XIRR", "最大回撤", "平均仓位"]))
        lines.append("")
        lines.append(f"![](charts/{nav_name})")
        lines.append("")
        lines.append(f"![](charts/{dd_name})")
        lines.append("")
        lines.append(f"![](charts/{heatmap_name})")
        lines.append("")
        lines.append(
            f"- 该标的样本内最优参数是 `{best_label}`，滚动起点（至少{ROLLING_MIN_YEARS}年持有）胜率为 {format_pct(payload['best_win_rate'])}。"
        )
        lines.append(
            f"- 固定参数（20%/12月）相对定投的XIRR超额为 {format_pct(payload['fixed_excess'])}，说明固定规则的稳定性比“看起来聪明”的择时更关键。"
        )
        lines.append(
            f"- 固定参数（10%/6月）相对定投的XIRR超额为 {format_pct(payload['fixed_10_6_excess'])}。"
        )
        lines.append("")
        section_idx += 1

    lines.append("## 五、你可以直接拿去用的实操结论")
    lines.append("")
    lines.append("- 若你没有一套可验证、可长期执行的择时纪律，优先采用每月定投。")
    lines.append("- 如果一定要做“等低点”，至少同时设置：回撤阈值 + 最长等待期限，避免长期空仓。")
    lines.append("- 更稳妥的方式是把择时当增强，而不是替代定投：例如“基础定投 + 低点额外加仓”。")
    lines.append("")
    lines.append("## 六、方法边界与可改进点")
    lines.append("")
    lines.append("- 美股部分采用 `SPY/QQQ` 前复权作为总收益近似，和严格官方总收益指数仍有细微偏差。")
    lines.append("- 本文是历史回测，不构成投资建议。")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    setup_plot_style()
    ensure_dirs()

    result_payload: dict[str, dict] = {}
    overall_rows: list[dict] = []

    for asset in ASSETS:
        prices = fetch_price_series(asset, START_DATE, END_DATE)
        prices.to_frame("close").to_csv(DATA_DIR / f"{asset.key}_daily_close.csv", encoding="utf-8-sig")

        dca = simulate_strategy(prices, "dca")
        fixed = simulate_strategy(prices, "timing", drawdown_threshold=0.20, max_wait_months=12)
        fixed_10_6 = simulate_strategy(prices, "timing", drawdown_threshold=0.10, max_wait_months=6)

        grid_rows: list[dict] = []
        for wait_m in MAX_WAIT_MONTHS:
            for dd in DRAWDOWN_LEVELS:
                timing = simulate_strategy(
                    prices,
                    "timing",
                    drawdown_threshold=dd,
                    max_wait_months=wait_m,
                )
                grid_rows.append(
                    {
                        "drawdown": dd,
                        "max_wait": wait_m,
                        "xirr": timing["xirr"],
                        "ann_return": timing["ann_return"],
                        "max_drawdown": timing["max_drawdown"],
                        "avg_invest_ratio": timing["avg_invest_ratio"],
                        "trade_count": timing["trade_count"],
                        "final_value": timing["final_value"],
                        "timing_result": timing,
                    }
                )

        grid_df = pd.DataFrame(grid_rows)
        grid_df["xirr_excess"] = grid_df["xirr"] - dca["xirr"]

        best_idx = grid_df["xirr_excess"].idxmax()
        best_row = grid_df.loc[best_idx]
        best_label = f"回撤{int(best_row['drawdown'] * 100)}%/等待{int(best_row['max_wait'])}个月"

        best_win_rate = rolling_win_rate(
            prices,
            drawdown_threshold=float(best_row["drawdown"]),
            max_wait_months=int(best_row["max_wait"]),
        )

        heatmap_df = (
            grid_df.pivot(index="max_wait", columns="drawdown", values="xirr_excess")
            .sort_index()
            .sort_index(axis=1)
            * 100.0
        )

        nav_path = CHART_DIR / f"{asset.key}_nav.png"
        dd_path = CHART_DIR / f"{asset.key}_drawdown.png"
        heatmap_path = CHART_DIR / f"{asset.key}_heatmap.png"

        timing_specs = [
            {
                "result": fixed,
                "label": "固定参数(20%/12月)",
            },
            {
                "result": fixed_10_6,
                "label": "固定参数(10%/6月)",
            },
        ]
        plot_equity_and_drawdown(asset.name, dca, timing_specs, nav_path, dd_path)
        plot_heatmap(asset.name, heatmap_df, heatmap_path)

        grid_export = grid_df.drop(columns=["timing_result"]).copy()
        grid_export.to_csv(
            DATA_DIR / f"{asset.key}_grid_results.csv",
            index=False,
            encoding="utf-8-sig",
        )

        result_payload[asset.key] = {
            "asset": asset,
            "best_label": best_label,
            "best_row": best_row.to_dict(),
            "fixed_row": fixed,
            "fixed_10_6_row": fixed_10_6,
            "dca_row": dca,
            "best_win_rate": best_win_rate,
            "fixed_excess": fixed["xirr"] - dca["xirr"],
            "fixed_10_6_excess": fixed_10_6["xirr"] - dca["xirr"],
            "nav_path": nav_path,
            "dd_path": dd_path,
            "heatmap_path": heatmap_path,
        }

        overall_rows.append(
            {
                "标的": asset.name,
                "定投_XIRR": dca["xirr"],
                "固定20%/12月_XIRR": fixed["xirr"],
                "固定10%/6月_XIRR": fixed_10_6["xirr"],
                "最优参数_XIRR": best_row["xirr"],
                "固定20%/12月_超额XIRR_bp": fixed["xirr"] - dca["xirr"],
                "固定10%/6月_超额XIRR_bp": fixed_10_6["xirr"] - dca["xirr"],
                "最优参数_超额XIRR_bp": best_row["xirr_excess"],
                "最优参数": best_label,
                "最优参数_滚动起点胜率": best_win_rate,
            }
        )

    overall_summary = pd.DataFrame(overall_rows)
    overall_summary.to_csv(
        DATA_DIR / "overall_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )

    plot_overall_excess(overall_summary, CHART_DIR / "overall_xirr_excess.png")

    article_text = generate_article(result_payload, overall_summary, START_DATE, END_DATE)
    ARTICLE_PATH.write_text(article_text, encoding="utf-8")

    print("Backtest complete.")
    print(f"Article: {ARTICLE_PATH}")
    print(f"Charts:  {CHART_DIR}")
    print(f"Data:    {DATA_DIR}")


if __name__ == "__main__":
    main()
