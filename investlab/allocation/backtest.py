#!/usr/bin/env python3
"""Backtest engine for signal-driven asset allocation with updated parameters.

Updated parameters (2026-03-17):
    cash = 2% (fixed)
    gold = 8% (fixed)
    usBond = 8% (fixed)
    usStock = 20% + 30% * xUsPremium (range 20%-50%)
    cnStock = 20% + remaining * yCnSignal (minimum 20%)
    cnBond = remaining * (1 - yCnSignal)

Includes:
1. Lumpsum backtest with multiple horizons
2. Rolling window validation (7-year quarterly rebalance)
3. Quarterly DCA simulation (¥10,000 per quarter)
4. Multiple benchmark comparisons (CSI800, 50/50, 80/20, S&P500)
5. Comprehensive metrics calculation
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import akshare as ak
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from investlab.allocation.calculator import target_weights
from investlab.allocation.signals import build_us_signal_series, build_cn_signal_series

plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "Arial Unicode MS",
]
plt.rcParams["axes.unicode_minus"] = False

# Backtest settings
INITIAL_CAPITAL = 10_000.0
REBALANCE_THRESHOLD = 0.05
PERCENTILE_WINDOW = 120
QUARTER_MONTHS = {3, 6, 9, 12}

# Benchmark definitions
BENCHMARKS = {
    "csi800": "中证800",
    "cn50_50": "中股中债50/50",
    "cn80_20": "中股中债80/20",
    "sp500": "标普500(RMB)",
}

# Asset colors for visualization
ASSET_COLORS = {
    "cash": "#6FAF9F",
    "gold": "#E6D58A",
    "cnBond": "#AEB6D6",
    "cnStock": "#5E93CF",
    "usBond": "#DFA0AC",
    "usStock": "#D77A6C",
}

ASSET_LABELS = {
    "cash": "现金",
    "gold": "黄金",
    "cnBond": "中债",
    "cnStock": "A股",
    "usBond": "美债",
    "usStock": "美股",
}


@dataclass
class BacktestResult:
    """Container for backtest results."""

    label: str
    start_month: pd.Period
    end_month: pd.Period
    nav: pd.Series
    monthly_returns: pd.Series
    rebalances: int
    metrics: Dict[str, float]
    chart_path: Optional[Path] = None


@dataclass
class DCAResult:
    """Container for DCA backtest results."""

    label: str
    start_month: pd.Period
    end_month: pd.Period
    nav: pd.Series
    invested: float
    end_value: float
    xirr: float
    max_drawdown: float
    cashflows: List[Tuple[pd.Timestamp, float]]


def rolling_percentile(series: pd.Series, window: int) -> pd.Series:
    """Calculate rolling percentile rank (0-1)."""
    values = pd.to_numeric(series, errors="coerce")
    out = []
    for i, val in enumerate(values):
        if pd.isna(val):
            out.append(np.nan)
            continue
        hist = values.iloc[max(0, i - window + 1) : i + 1].dropna()
        if hist.empty:
            out.append(np.nan)
            continue
        out.append(float((hist <= val).sum() / len(hist)))
    return pd.Series(out, index=values.index)


def month_end(
    df: pd.DataFrame, date_col: str, value_col: str, out_col: str
) -> pd.DataFrame:
    """Extract month-end values."""
    out = df[[date_col, value_col]].copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    out[value_col] = pd.to_numeric(out[value_col], errors="coerce")
    out = out.dropna(subset=[date_col, value_col]).sort_values(date_col)
    out["month"] = out[date_col].dt.to_period("M")
    out = out.groupby("month", as_index=False).last()
    out = out[["month", value_col]].rename(columns={value_col: out_col})
    return out


def fetch_usdcny_monthly() -> pd.DataFrame:
    """Fetch USD/CNY exchange rate (monthly)."""
    fx = pd.DataFrame(ak.currency_boc_safe())
    date_col = fx.columns[0]
    usd_col = fx.columns[1]
    out = month_end(fx, date_col, usd_col, "usdcny_per_100")
    out["usdcny"] = out["usdcny_per_100"] / 100.0
    return out[["month", "usdcny"]]


def fetch_us_close_monthly(symbol: str, out_col: str) -> pd.DataFrame:
    """Fetch US index monthly close prices."""
    df = pd.DataFrame(ak.index_us_stock_sina(symbol=symbol))
    return month_end(df, "date", "close", out_col)


def fetch_cn_index_monthly() -> Tuple[pd.DataFrame, str]:
    """Fetch Chinese stock index monthly prices (prefer CSI800, fallback to HS300)."""
    try:
        csi = pd.DataFrame(ak.stock_zh_index_daily(symbol="sh000906"))
        csi_m = month_end(csi, "date", "close", "cn_stock_price")
        if len(csi_m) > 60:
            return csi_m, "CSI800"
    except Exception:
        pass

    hs300 = pd.DataFrame(ak.stock_zh_index_daily(symbol="sh000300"))
    hs300_m = month_end(hs300, "date", "close", "cn_stock_price")
    return hs300_m, "HS300"


def fetch_cn_etf_monthly(symbol: str, out_col: str) -> pd.DataFrame:
    """Fetch Chinese ETF monthly prices."""
    df = pd.DataFrame(
        ak.fund_etf_hist_em(
            symbol=symbol,
            period="daily",
            start_date="20080101",
            end_date="20301231",
            adjust="qfq",
        )
    )
    date_col = df.columns[0]
    close_col = df.columns[2]
    return month_end(df, date_col, close_col, out_col)


def build_panel() -> Tuple[pd.DataFrame, str]:
    """Build unified panel with all required data."""
    cn_stock, cn_index_used = fetch_cn_index_monthly()

    us_stock = fetch_us_close_monthly(".INX", "usStock_usd")
    us_bond = fetch_us_close_monthly("TLT", "usBond_usd")
    fx = fetch_usdcny_monthly()
    cn_bond = fetch_cn_etf_monthly("511010", "cnBond_price")
    gold = fetch_cn_etf_monthly("518880", "gold_price")

    x_signal = build_us_signal_series()
    y_signal = build_cn_signal_series()

    panel = (
        cn_stock.merge(us_stock, on="month", how="inner")
        .merge(us_bond, on="month", how="inner")
        .merge(fx, on="month", how="inner")
        .merge(cn_bond, on="month", how="inner")
        .merge(gold, on="month", how="inner")
        .merge(x_signal, on="month", how="inner")
        .merge(y_signal, on="month", how="inner")
        .sort_values("month")
        .reset_index(drop=True)
    )

    panel["usStock_rmb"] = panel["usStock_usd"] * panel["usdcny"]
    panel["usBond_rmb"] = panel["usBond_usd"] * panel["usdcny"]
    panel["cash_ret"] = 0.0  # Assume 0% cash return for simplicity
    panel = panel.dropna().reset_index(drop=True)
    return panel, cn_index_used


def calculate_metrics(nav: pd.Series, monthly_returns: pd.Series) -> Dict[str, float]:
    """Calculate performance metrics from NAV series."""
    months = len(nav) - 1
    years = months / 12 if months > 0 else np.nan
    total_return = float(nav.iloc[-1] / nav.iloc[0] - 1)
    cagr = (
        float((nav.iloc[-1] / nav.iloc[0]) ** (1 / years) - 1) if years > 0 else np.nan
    )
    vol = (
        float(monthly_returns.std(ddof=1) * np.sqrt(12))
        if len(monthly_returns) > 1
        else np.nan
    )
    sharpe = float((monthly_returns.mean() * 12) / vol) if vol and vol > 0 else np.nan
    dd = nav / nav.cummax() - 1
    max_dd = float(dd.min())

    return {
        "start_value": float(nav.iloc[0]),
        "end_value": float(nav.iloc[-1]),
        "total_return": total_return,
        "cagr": cagr,
        "annual_vol": vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "months": months,
    }


def run_lumpsum_backtest(
    panel: pd.DataFrame, start_month: pd.Period, label: str
) -> BacktestResult:
    """Run lumpsum backtest from start_month."""
    df = panel[panel["month"] >= start_month].copy()
    if len(df) < 3:
        raise ValueError(f"{label} 可用样本不足")

    asset_cols = [
        "cash_ret",
        "gold_ret",
        "cnBond_ret",
        "cnStock_ret",
        "usBond_ret",
        "usStock_ret",
    ]

    first = df.iloc[0]
    w0 = target_weights(first["x_signal"], first["y_signal"])
    holdings = pd.Series(
        {
            "cash_ret": INITIAL_CAPITAL * w0["cash"],
            "gold_ret": INITIAL_CAPITAL * w0["gold"],
            "cnBond_ret": INITIAL_CAPITAL * w0["cnBond"],
            "cnStock_ret": INITIAL_CAPITAL * w0["cnStock"],
            "usBond_ret": INITIAL_CAPITAL * w0["usBond"],
            "usStock_ret": INITIAL_CAPITAL * w0["usStock"],
        }
    )

    nav_records = [(first["month"], float(holdings.sum()))]
    rebalances = 0

    for i in range(1, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]

        rel = pd.Series(
            {
                "cash_ret": 1.0 + float(row["cash_ret"]),
                "gold_ret": float(row["gold_price"]) / float(prev["gold_price"]),
                "cnBond_ret": float(row["cnBond_price"]) / float(prev["cnBond_price"]),
                "cnStock_ret": float(row["cn_stock_price"])
                / float(prev["cn_stock_price"]),
                "usBond_ret": float(row["usBond_rmb"]) / float(prev["usBond_rmb"]),
                "usStock_ret": float(row["usStock_rmb"]) / float(prev["usStock_rmb"]),
            }
        )

        holdings = holdings * rel
        value = float(holdings.sum())
        current_w = holdings / value

        tw = target_weights(row["x_signal"], row["y_signal"])
        target_w = pd.Series(
            {
                "cash_ret": tw["cash"],
                "gold_ret": tw["gold"],
                "cnBond_ret": tw["cnBond"],
                "cnStock_ret": tw["cnStock"],
                "usBond_ret": tw["usBond"],
                "usStock_ret": tw["usStock"],
            }
        )

        if float((current_w - target_w).abs().max()) > REBALANCE_THRESHOLD:
            holdings = value * target_w
            rebalances += 1

        nav_records.append((row["month"], float(holdings.sum())))

    nav_df = pd.DataFrame(nav_records, columns=["month", "value"]).set_index("month")
    nav = nav_df["value"]
    monthly_returns = nav.pct_change().dropna()

    metrics = calculate_metrics(nav, monthly_returns)
    metrics["rebalances"] = float(rebalances)

    return BacktestResult(
        label=label,
        start_month=df.iloc[0]["month"],
        end_month=df.iloc[-1]["month"],
        nav=nav,
        monthly_returns=monthly_returns,
        rebalances=rebalances,
        metrics=metrics,
    )


def month_end_date(p: pd.Period) -> pd.Timestamp:
    """Convert period to month-end timestamp."""
    return p.to_timestamp(how="end").normalize()


def xirr(cashflows: List[Tuple[pd.Timestamp, float]]) -> float:
    """Calculate internal rate of return for irregular cash flows."""

    def xnpv(rate: float) -> float:
        t0 = cashflows[0][0]
        return sum(cf / ((1 + rate) ** ((t - t0).days / 365.0)) for t, cf in cashflows)

    low, high = -0.999, 5.0
    f_low, f_high = xnpv(low), xnpv(high)
    if np.sign(f_low) == np.sign(f_high):
        high = 20.0
        f_high = xnpv(high)
        if np.sign(f_low) == np.sign(f_high):
            return np.nan

    for _ in range(200):
        mid = (low + high) / 2
        f_mid = xnpv(mid)
        if abs(f_mid) < 1e-9:
            return mid
        if np.sign(f_mid) == np.sign(f_low):
            low, f_low = mid, f_mid
        else:
            high, f_high = mid, f_mid
    return (low + high) / 2


def run_dca_backtest(
    panel: pd.DataFrame, start_month: pd.Period, label: str
) -> DCAResult:
    """Run quarterly DCA backtest from start_month."""
    df = panel[panel["month"] >= start_month].copy()
    if len(df) < 3:
        raise ValueError(f"{label} 可用样本不足")

    holdings = pd.Series(
        {
            "cash": 0.0,
            "gold": 0.0,
            "cnBond": 0.0,
            "cnStock": 0.0,
            "usBond": 0.0,
            "usStock": 0.0,
        }
    )
    nav_records = []
    invested = 0.0
    rebalances = 0
    cashflows: List[Tuple[pd.Timestamp, float]] = []

    for i in range(len(df)):
        row = df.iloc[i]
        m = row["month"]

        # Quarterly contribution
        if m.month in QUARTER_MONTHS:
            tw = target_weights(row["x_signal"], row["y_signal"])
            contribution = 10_000
            holdings = holdings + contribution * pd.Series(
                {
                    "cash": tw["cash"],
                    "gold": tw["gold"],
                    "cnBond": tw["cnBond"],
                    "cnStock": tw["cnStock"],
                    "usBond": tw["usBond"],
                    "usStock": tw["usStock"],
                }
            )
            invested += contribution
            cashflows.append((month_end_date(m), -contribution))
            # Rebalance to target weights
            total_value = float(holdings.sum())
            holdings = total_value * pd.Series(
                {
                    "cash": tw["cash"],
                    "gold": tw["gold"],
                    "cnBond": tw["cnBond"],
                    "cnStock": tw["cnStock"],
                    "usBond": tw["usBond"],
                    "usStock": tw["usStock"],
                }
            )
            rebalances += 1

        nav_records.append((m, float(holdings.sum())))

        # Apply returns to next period
        if i == len(df) - 1:
            break

        nxt = df.iloc[i + 1]
        rel = pd.Series(
            {
                "cash": 1.0 + float(nxt["cash_ret"]),
                "gold": float(nxt["gold_price"]) / float(row["gold_price"]),
                "cnBond": float(nxt["cnBond_price"]) / float(row["cnBond_price"]),
                "cnStock": float(nxt["cn_stock_price"]) / float(row["cn_stock_price"]),
                "usBond": float(nxt["usBond_rmb"]) / float(row["usBond_rmb"]),
                "usStock": float(nxt["usStock_rmb"]) / float(row["usStock_rmb"]),
            }
        )
        holdings = holdings * rel

    nav_df = pd.DataFrame(nav_records, columns=["month", "value"]).set_index("month")
    nav = nav_df["value"]
    end_value = float(nav.iloc[-1])
    cashflows.append((month_end_date(df.iloc[-1]["month"]), end_value))
    irr = xirr(cashflows)

    dd = nav / nav.cummax() - 1
    max_dd = float(dd.min())

    return DCAResult(
        label=label,
        start_month=df.iloc[0]["month"],
        end_month=df.iloc[-1]["month"],
        nav=nav,
        invested=invested,
        end_value=end_value,
        xirr=irr,
        max_drawdown=max_dd,
        cashflows=cashflows,
    )


def benchmark_nav_from_prices(
    df: pd.DataFrame, key: str, start_value: float
) -> pd.Series:
    """Calculate benchmark NAV from price data."""
    if key == "csi800":
        px = df["cn_stock_price"]
        return start_value * (px / float(px.iloc[0]))
    if key == "sp500":
        px = df["usStock_rmb"]
        return start_value * (px / float(px.iloc[0]))

    stock_rel = df["cn_stock_price"] / float(df["cn_stock_price"].iloc[0])
    bond_rel = df["cnBond_price"] / float(df["cnBond_price"].iloc[0])
    if key == "cn50_50":
        return start_value * (0.5 * stock_rel + 0.5 * bond_rel)
    if key == "cn80_20":
        return start_value * (0.8 * stock_rel + 0.2 * bond_rel)
    raise ValueError(key)


def run_benchmark_dca(
    df: pd.DataFrame, key: str
) -> Tuple[pd.Series, float, List[Tuple[pd.Timestamp, float]]]:
    """Run DCA simulation for benchmark strategies."""
    nav, invested, cf = [], 0.0, []

    if key in {"csi800", "sp500"}:
        shares = 0.0
        px_col = "cn_stock_price" if key == "csi800" else "usStock_rmb"
        for _, row in df.iterrows():
            m = row["month"]
            px = float(row[px_col])
            if m.month in QUARTER_MONTHS:
                shares += 10_000 / px
                invested += 10_000
                cf.append((month_end_date(m), -10_000.0))
            nav.append(shares * px)
        nav_s = pd.Series(nav, index=df["month"])
        cf.append((month_end_date(df.iloc[-1]["month"]), float(nav_s.iloc[-1])))
        return nav_s, invested, cf

    # cn50_50 / cn80_20 with quarterly rebalance
    if key == "cn50_50":
        sw, bw = 0.5, 0.5
    elif key == "cn80_20":
        sw, bw = 0.8, 0.2
    else:
        raise ValueError(key)

    hs, hb = 0.0, 0.0
    for i in range(len(df)):
        row = df.iloc[i]
        m = row["month"]
        ps = float(row["cn_stock_price"])
        pb = float(row["cnBond_price"])

        if m.month in QUARTER_MONTHS:
            hs += (10_000 * sw) / ps
            hb += (10_000 * bw) / pb
            invested += 10_000
            cf.append((month_end_date(m), -10_000.0))
            total = hs * ps + hb * pb
            hs = (total * sw) / ps
            hb = (total * bw) / pb

        nav.append(hs * ps + hb * pb)

    nav_s = pd.Series(nav, index=df["month"])
    cf.append((month_end_date(df.iloc[-1]["month"]), float(nav_s.iloc[-1])))
    return nav_s, invested, cf


def plot_horizon_comparison(
    df: pd.DataFrame,
    strategy_nav: pd.Series,
    bench_navs: Dict[str, pd.Series],
    title: str,
    out_path: Path,
) -> None:
    """Plot strategy vs benchmarks with drawdown."""
    idx = strategy_nav.index.astype(str)
    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [3, 1]}
    )

    ax1.plot(
        idx,
        strategy_nav / strategy_nav.iloc[0],
        color="#0B4F9C",
        linewidth=2.2,
        label="策略",
    )
    for k, nav in bench_navs.items():
        ax1.plot(idx, nav / nav.iloc[0], linewidth=1.5, label=BENCHMARKS[k])
    ax1.set_title(title)
    ax1.set_ylabel("净值")
    ax1.grid(alpha=0.25)
    ax1.legend(ncol=3, fontsize=9)

    dd = strategy_nav / strategy_nav.cummax() - 1
    ax2.plot(idx, dd * 100, color="#B24D4D", linewidth=1.5, label="策略回撤")
    ax2.set_ylabel("回撤%")
    ax2.grid(alpha=0.25)
    ax2.legend()
    step = max(1, len(idx) // 12)
    xt = np.arange(0, len(idx), step)
    ax2.set_xticks(xt)
    ax2.set_xticklabels([idx[i] for i in xt], rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(out_path, dpi=180)
    plt.close(fig)
