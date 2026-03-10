from __future__ import annotations

import akshare as ak
import pandas as pd

from investlab.models import AssetSpec


DEFAULT_ASSETS: list[AssetSpec] = [
    AssetSpec("H00300", "沪深300全收益", "csindex_tri", "H00300", True),
    AssetSpec("H00906", "中证800全收益", "csindex_tri", "H00906", True),
    AssetSpec("H00905", "中证500全收益", "csindex_tri", "H00905", True),
    AssetSpec("SPY", "标普500（SPY前复权）", "us_etf_qfq", "SPY", True),
    AssetSpec("QQQ", "纳指100（QQQ前复权）", "us_etf_qfq", "QQQ", True),
]


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
    series = series.dropna()
    # Adjusted US data occasionally contains artifacts <= 0; drop for stability.
    series = series[series > 0]
    return series


def select_assets(asset_keys: list[str] | None = None) -> list[AssetSpec]:
    if not asset_keys:
        return DEFAULT_ASSETS

    normalized = {x.strip().upper() for x in asset_keys if x.strip()}
    assets = [x for x in DEFAULT_ASSETS if x.key.upper() in normalized]
    if not assets:
        raise ValueError(f"No matched assets for keys: {asset_keys}")
    return assets
