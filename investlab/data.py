from __future__ import annotations

import akshare as ak
import pandas as pd
from dataclasses import dataclass

from investlab.core.price_loading import (
    NormalizePriceFrameInput,
    fetch_fred_closes,
    fetch_yahoo_index_closes,
    normalize_price_frame,
)
from investlab.core.asset_registry import REGISTRY
from investlab.models import AssetSpec


DEFAULT_ASSETS: list[AssetSpec] = [
    AssetSpec(
        entry.compute_key,
        entry.compute_name,
        entry.compute_source,
        entry.compute_symbol,
        entry.compute_total_return,
    )
    for entry in REGISTRY
    if entry.compute_key is not None
    and entry.compute_name is not None
    and entry.compute_source is not None
    and entry.compute_symbol is not None
]


@dataclass(frozen=True, slots=True)
class UnknownAssetError(ValueError):
    unknown_keys: tuple[str, ...]
    available_keys: tuple[str, ...]

    def __str__(self) -> str:
        joined_unknown = ",".join(self.unknown_keys)
        joined_available = ",".join(self.available_keys)
        return f"Unknown asset key(s): {joined_unknown}. Available asset keys: {joined_available}"


def fetch_price_series(spec: AssetSpec, start_date: str, end_date: str) -> pd.Series:
    match spec.source:
        case "csindex_tri":
            raw = ak.stock_zh_index_hist_csindex(
                symbol=spec.symbol,
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
            )
            return normalize_price_frame(
                raw,
                NormalizePriceFrameInput(
                    date_column="日期",
                    close_column="收盘",
                    series_name=spec.key,
                    start_date=start_date,
                    end_date=end_date,
                ),
            )
        case "us_etf_qfq":
            raw = ak.stock_us_daily(symbol=spec.symbol, adjust="qfq")
            return normalize_price_frame(
                raw,
                NormalizePriceFrameInput(
                    date_column="date",
                    close_column="close",
                    series_name=spec.key,
                    start_date=start_date,
                    end_date=end_date,
                ),
            )
        case "fred":
            closes = fetch_fred_closes(spec.symbol, int(start_date[:4]), int(end_date[:4]))
        case "yahoo_index":
            closes = fetch_yahoo_index_closes(
                spec.symbol, int(start_date[:4]), int(end_date[:4])
            )
        case _:
            raise ValueError(f"Unsupported source: {spec.source}")

    return pd.Series(closes.astype(float).to_numpy(), index=closes.index, name=spec.key)


def select_assets(asset_keys: list[str] | None = None) -> list[AssetSpec]:
    if not asset_keys:
        return DEFAULT_ASSETS

    normalized = tuple(x.strip().upper() for x in asset_keys if x.strip())
    selected_by_key = {asset.key.upper(): asset for asset in DEFAULT_ASSETS}
    assets = [selected_by_key[key] for key in normalized if key in selected_by_key]
    unknown_keys = tuple(key for key in normalized if key not in selected_by_key)
    if unknown_keys:
        raise UnknownAssetError(
            unknown_keys=unknown_keys,
            available_keys=tuple(asset.key for asset in DEFAULT_ASSETS),
        )
    return assets
