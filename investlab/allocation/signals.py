"""Signal calculation for asset allocation.

Includes:
1. Chinese market signal (yCnSignal) based on CSI800 FED premium
2. US market signal (xUsPremium) based on S&P500 risk premium
"""

from __future__ import annotations

import re
from functools import lru_cache

import akshare as ak
import pandas as pd
import requests


def rolling_percentile(series: pd.Series, window: int) -> pd.Series:
    """Calculate rolling percentile rank (0-1)."""
    values = pd.to_numeric(series, errors="coerce")
    out = []
    for i, val in enumerate(values):
        if pd.isna(val):
            out.append(pd.NA)
            continue
        hist = values.iloc[max(0, i - window + 1) : i + 1].dropna()
        if hist.empty:
            out.append(pd.NA)
            continue
        out.append(float((hist <= val).sum() / len(hist)))
    return pd.Series(out, index=values.index)


# Chinese signal functions
def fetch_csi800_monthly_pe(pe_type: str = "rolling") -> pd.DataFrame:
    """Fetch CSI800 monthly PE data."""
    pe_field_map = {"rolling": "滚动市盈率", "static": "静态市盈率"}
    pe_col = pe_field_map[pe_type]

    df = pd.DataFrame(ak.stock_index_pe_lg(symbol="中证800"))
    df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
    df[pe_col] = pd.to_numeric(df[pe_col], errors="coerce")
    df = df.dropna(subset=["日期", pe_col]).copy()
    df = df[df[pe_col] > 0].sort_values("日期")
    df["month"] = df["日期"].dt.to_period("M")

    monthly = df.groupby("month", as_index=False).last()[["month", "日期", pe_col]]
    monthly.columns = ["month", "日期", "pe"]
    monthly["equity_yield"] = 1 / monthly["pe"]
    return monthly[["month", "日期", "pe", "equity_yield"]]


def fetch_cn10y_monthly() -> pd.DataFrame:
    """Fetch Chinese 10-year bond yield (monthly)."""
    df = pd.DataFrame(ak.bond_zh_us_rate())
    df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
    df["中国国债收益率10年"] = pd.to_numeric(df["中国国债收益率10年"], errors="coerce")
    df = df.dropna(subset=["日期", "中国国债收益率10年"]).copy()
    df["month"] = df["日期"].dt.to_period("M")

    monthly = df.groupby("month", as_index=False).last()[
        ["month", "日期", "中国国债收益率10年"]
    ]
    monthly.columns = ["month", "日期", "cn10y"]
    monthly["rf"] = monthly["cn10y"] / 100
    return monthly[["month", "日期", "cn10y", "rf"]]


def build_cn_fed_series(pe_type: str = "rolling") -> pd.DataFrame:
    """Build Chinese FED premium series."""
    pe_df = fetch_csi800_monthly_pe(pe_type)
    rf_df = fetch_cn10y_monthly()
    merged = pe_df.merge(rf_df[["month", "rf", "cn10y"]], on="month", how="inner")
    merged["fed_premium"] = merged["equity_yield"] - merged["rf"]
    return merged.sort_values("日期").reset_index(drop=True)


def build_cn_signal_series(window: int = 120, pe_type: str = "rolling") -> pd.DataFrame:
    """Build yCnSignal series for Chinese market."""
    fed = build_cn_fed_series(pe_type)
    fed["month"] = fed["month"].astype("period[M]")
    fed = fed.sort_values("month").reset_index(drop=True)
    fed["y_signal"] = rolling_percentile(fed["fed_premium"], window)
    return fed[["month", "y_signal"]]


# US signal functions
@lru_cache(maxsize=1)
def fetch_us10y_monthly() -> pd.DataFrame:
    """Fetch US 10-year Treasury yield (monthly)."""
    rate_df = ak.bond_zh_us_rate()
    rate_df["日期"] = pd.to_datetime(rate_df["日期"], errors="coerce")
    rate_df["美国国债收益率10年"] = pd.to_numeric(
        rate_df["美国国债收益率10年"], errors="coerce"
    )
    rate_df = rate_df.dropna(subset=["日期", "美国国债收益率10年"]).copy()
    rate_df["month"] = rate_df["日期"].dt.to_period("M")

    monthly = (
        rate_df.sort_values("日期")
        .groupby("month", as_index=False)
        .last()[["month", "日期", "美国国债收益率10年"]]
    )
    monthly["rf"] = monthly["美国国债收益率10年"] / 100
    return monthly[["month", "日期", "rf"]]


def fetch_pe_yield_monthly(index_key: str = "sp500", timeout: int = 20) -> pd.DataFrame:
    """Fetch PE yield data from worldperatio.com."""
    index_urls = {
        "sp500": "https://worldperatio.com/index/sp-500/",
        "nasdaq100": "https://worldperatio.com/index/nasdaq-100/",
    }

    resp = requests.get(
        index_urls[index_key],
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; risk-premium/1.0)",
            "Accept": "text/html,*/*",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    html = resp.text

    m = re.search(r"detailPE_data\s*=\s*\[(.*?)\];\s*detailPE_data_avg", html, re.S)
    if not m:
        raise RuntimeError(f"无法解析 {index_key} 的 PE 数据")

    rows = re.findall(r"Date\.UTC\((\d+),\s*(\d+),\s*(\d+)\),\s*([0-9.]+)", m.group(1))
    if not rows:
        raise RuntimeError(f"{index_key} PE 数据为空")

    recs = []
    for y, m0, d, pe in rows:
        dt = pd.Timestamp(int(y), int(m0) + 1, int(d))
        pe_v = float(pe)
        if pe_v > 0:
            recs.append((dt, pe_v))

    df = pd.DataFrame(recs, columns=["date", "pe"]).sort_values("date")
    df["month"] = df["date"].dt.to_period("M")
    df["yield"] = 1 / df["pe"]
    return df[["month", "date", "yield"]]


def fetch_ret12m_monthly(index_key: str = "sp500") -> pd.DataFrame:
    """Fetch 12-month return series for US indices."""
    index_symbols = {"sp500": ".INX", "nasdaq100": ".NDX"}
    symbol = index_symbols[index_key]

    px = ak.index_us_stock_sina(symbol=symbol)
    px["date"] = pd.to_datetime(px["date"], errors="coerce")
    px["close"] = pd.to_numeric(px["close"], errors="coerce")
    px = px.dropna(subset=["date", "close"]).sort_values("date")
    px["month"] = px["date"].dt.to_period("M")

    monthly = px.groupby("month", as_index=False).last()[["month", "date", "close"]]
    monthly["yield"] = monthly["close"].pct_change(12)
    monthly = monthly[monthly["yield"].notna()].copy()
    return monthly[["month", "date", "yield"]]


def build_us_premium_series(
    index_key: str = "sp500", method: str = "pe"
) -> pd.DataFrame:
    """Build US risk premium series."""
    if method == "pe":
        yld = fetch_pe_yield_monthly(index_key)
    elif method == "ret12m":
        yld = fetch_ret12m_monthly(index_key)
    else:
        raise ValueError("method must be 'pe' or 'ret12m'")

    rf = fetch_us10y_monthly()
    merged = yld.merge(rf[["month", "rf"]], on="month", how="inner")
    merged["risk_premium"] = merged["yield"] - merged["rf"]
    return merged.sort_values("date").reset_index(drop=True)


def build_us_signal_series(window: int = 120, method: str = "pe") -> pd.DataFrame:
    """Build xUsPremium series for US market."""
    us = build_us_premium_series("sp500", method)
    us["month"] = us["month"].astype("period[M]")
    us = us.sort_values("month").reset_index(drop=True)
    us["x_signal"] = rolling_percentile(us["risk_premium"], window)
    return us[["month", "x_signal"]]


# Convenience functions
def get_signals(window: int = 120) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Get both US and CN signal series."""
    us_signal = build_us_signal_series(window)
    cn_signal = build_cn_signal_series(window)
    return us_signal, cn_signal
