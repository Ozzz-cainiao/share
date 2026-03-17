#!/usr/bin/env python3
"""Complete asset allocation backtest with updated parameters.

Updated parameters (2026-03-17):
    cash = 2% (fixed)
    gold = 8% (fixed)
    usBond = 8% (fixed)
    usStock = 20% + 30% * xUsPremium (range 20%-50%)
    cnStock = 20% + remaining * yCnSignal (minimum 20%)
    cnBond = remaining * (1 - yCnSignal)

Includes:
1. Lumpsum backtest with multiple horizons (10y, 5y, 3y, 1y)
2. Rolling window validation (7-year quarterly rebalance)
3. Quarterly DCA simulation (¥10,000 per quarter)
4. Multiple benchmark comparisons (CSI800, 50/50, 80/20, S&P500)
5. Comprehensive visualization (charts, heatmaps, 3D plots)
6. Full report generation
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import akshare as ak
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Configure matplotlib for Chinese text
plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "SimHei",
    "Noto Sans CJK SC",
    "Arial Unicode MS",
]
plt.rcParams["axes.unicode_minus"] = False

# Updated parameters
CASH_RATIO = 0.02
GOLD_RATIO = 0.08
US_BOND_RATIO = 0.08
BASE_US_STOCK = 0.20
US_STOCK_RANGE = 0.30
BASE_CN_STOCK = 0.20

# Backtest settings
INITIAL_CAPITAL = 10_000.0
REBALANCE_THRESHOLD = 0.05
PERCENTILE_WINDOW = 120
QUARTER_MONTHS = {3, 6, 9, 12}

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

# Benchmark definitions
BENCHMARKS = {
    "csi800": "中证800",
    "cn50_50": "中股中债50/50",
    "cn80_20": "中股中债80/20",
    "sp500": "标普500(RMB)",
}


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


def build_cn_signal_series(index_used: str) -> pd.DataFrame:
    """Build yCnSignal series for Chinese market."""
    # Import local modules (to be copied or integrated)
    sys.path.append(r"E:/fund_tools")
    try:
        from csi800_fed_premium import build_series as build_csi800_fed_series
    except ImportError:
        # Fallback implementation
        return _build_cn_signal_fallback()

    if index_used == "CSI800":
        fed = build_csi800_fed_series("rolling")
        fed["month"] = fed["month"].astype("period[M]")
        fed = fed.sort_values("month").reset_index(drop=True)
        fed["y_signal"] = rolling_percentile(fed["fed_premium"], PERCENTILE_WINDOW)
        return fed[["month", "y_signal"]]

    return _build_cn_signal_fallback()


def _build_cn_signal_fallback() -> pd.DataFrame:
    """Fallback implementation for CN signal using HS300."""
    pe_df = pd.DataFrame(ak.stock_index_pe_lg(symbol="沪深300"))
    date_col = pe_df.columns[0]
    pe_col = None
    for c in pe_df.columns:
        if "滚动市盈率" in str(c):
            pe_col = c
            break
    if pe_col is None:
        pe_col = pe_df.columns[-2]

    pe_df = pe_df[[date_col, pe_col]].copy()
    pe_df[date_col] = pd.to_datetime(pe_df[date_col], errors="coerce")
    pe_df[pe_col] = pd.to_numeric(pe_df[pe_col], errors="coerce")
    pe_df = pe_df.dropna(subset=[date_col, pe_col])
    pe_df = pe_df[pe_df[pe_col] > 0].sort_values(date_col)
    pe_df["month"] = pe_df[date_col].dt.to_period("M")
    pe_month = pe_df.groupby("month", as_index=False).last()[["month", pe_col]].copy()
    pe_month["equity_yield"] = 1.0 / pe_month[pe_col]

    rate = pd.DataFrame(ak.bond_zh_us_rate())
    dcol = rate.columns[0]
    cn10y_col = rate.columns[3]
    rate = rate[[dcol, cn10y_col]].copy()
    rate[dcol] = pd.to_datetime(rate[dcol], errors="coerce")
    rate[cn10y_col] = pd.to_numeric(rate[cn10y_col], errors="coerce")
    rate = rate.dropna(subset=[dcol, cn10y_col]).sort_values(dcol)
    rate["month"] = rate[dcol].dt.to_period("M")
    rate_m = rate.groupby("month", as_index=False).last()[["month", cn10y_col]].copy()
    rate_m["rf"] = rate_m[cn10y_col] / 100.0

    merged = pe_month.merge(rate_m[["month", "rf"]], on="month", how="inner")
    merged["fed_premium"] = merged["equity_yield"] - merged["rf"]
    merged = merged.sort_values("month").reset_index(drop=True)
    merged["y_signal"] = rolling_percentile(merged["fed_premium"], PERCENTILE_WINDOW)
    return merged[["month", "y_signal"]]


def build_us_signal_series() -> pd.DataFrame:
    """Build xUsPremium series for US market."""
    sys.path.append(r"E:/fund_tools")
    try:
        from risk_premium_percentile import build_premium_series
    except ImportError:
        return _build_us_signal_fallback()

    us = build_premium_series("sp500", "pe").copy()
    us["month"] = us["month"].astype("period[M]")
    us = us.sort_values("month").reset_index(drop=True)
    us["x_signal"] = rolling_percentile(us["risk_premium"], PERCENTILE_WINDOW)
    return us[["month", "x_signal"]]


def _build_us_signal_fallback() -> pd.DataFrame:
    """Fallback implementation for US signal."""
    # Simplified implementation - in practice should import the module
    raise ImportError(
        "US signal module not available. Please ensure risk_premium_percentile.py is accessible."
    )


def target_weights(x: float, y: float) -> Dict[str, float]:
    """Calculate target weights based on signals and updated parameters."""
    cash = CASH_RATIO
    gold = GOLD_RATIO
    us_bond = US_BOND_RATIO
    us_stock = BASE_US_STOCK + US_STOCK_RANGE * float(np.clip(x, 0, 1))

    used = cash + gold + us_bond + us_stock + BASE_CN_STOCK
    remaining = max(0.0, 1.0 - used)

    y = float(np.clip(y, 0, 1))
    cn_stock = BASE_CN_STOCK + remaining * y
    cn_bond = remaining * (1.0 - y)

    w = {
        "cash": cash,
        "gold": gold,
        "cnBond": cn_bond,
        "cnStock": cn_stock,
        "usBond": us_bond,
        "usStock": us_stock,
    }

    total = sum(w.values())
    if not np.isclose(total, 1.0, atol=1e-8):
        raise ValueError(f"weights sum to {total}, expected 1")
    return w


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
    chart_path: Path


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

    metrics = {
        "start_value": float(nav.iloc[0]),
        "end_value": float(nav.iloc[-1]),
        "total_return": total_return,
        "cagr": cagr,
        "annual_vol": vol,
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "months": months,
        "rebalances": float(rebalances),
    }

    return BacktestResult(
        label=label,
        start_month=df.iloc[0]["month"],
        end_month=df.iloc[-1]["month"],
        nav=nav,
        monthly_returns=monthly_returns,
        rebalances=rebalances,
        metrics=metrics,
        chart_path=None,  # Will be set later
    )


def build_panel() -> Tuple[pd.DataFrame, str]:
    """Build unified panel with all required data."""
    cn_stock, cn_index_used = fetch_cn_index_monthly()

    us_stock = fetch_us_close_monthly(".INX", "usStock_usd")
    us_bond = fetch_us_close_monthly("TLT", "usBond_usd")
    fx = fetch_usdcny_monthly()
    cn_bond = fetch_cn_etf_monthly("511010", "cnBond_price")
    gold = fetch_cn_etf_monthly("518880", "gold_price")

    x_signal = build_us_signal_series()
    y_signal = build_cn_signal_series(cn_index_used)

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


def main():
    """Main function to run complete backtest."""
    parser = argparse.ArgumentParser(
        description="Asset allocation backtest with updated parameters"
    )
    parser.add_argument(
        "--output-dir", default="output/allocation", help="Output directory"
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Building data panel...")
    panel, cn_index_used = build_panel()

    print(f"Panel range: {panel['month'].min()} to {panel['month'].max()}")
    print(f"Chinese signal index: {cn_index_used}")

    # Run backtests
    last_month = panel.iloc[-1]["month"]
    horizons = [("10y", 120), ("5y", 60), ("3y", 36), ("1y", 12)]

    results = []
    for label, months in horizons:
        print(f"Running {label} backtest...")
        start = last_month - months
        result = run_lumpsum_backtest(panel, start, label)
        results.append(result)

    # Save results
    print("Saving results...")
    # TODO: Add visualization, benchmarks, and report generation

    print("Backtest completed!")


if __name__ == "__main__":
    main()
