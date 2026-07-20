from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, assert_never

import akshare as ak
import pandas as pd  # noqa: PANDAS_OK

from investlab.data import fetch_price_series
from investlab.models import AssetSpec
from investlab.technical_timing.models import TechnicalTimingError, TimingDataSource


@dataclass(frozen=True, slots=True)
class TimingAsset:
    key: str
    name: str
    akshare_symbol: str
    close_proxy_spec: AssetSpec | None = None


PAPER_ASSETS: Final[tuple[TimingAsset, ...]] = (
    TimingAsset(
        key="large-cap",
        name="沪深300",
        akshare_symbol="sh000300",
        close_proxy_spec=AssetSpec(
            "H00300", "沪深300全收益", "csindex_tri", "H00300", True
        ),
    ),
    TimingAsset(
        key="mid-cap",
        name="中证500",
        akshare_symbol="sh000905",
        close_proxy_spec=AssetSpec(
            "H00905", "中证500全收益", "csindex_tri", "H00905", True
        ),
    ),
    TimingAsset(
        key="small-cap",
        name="中证1000",
        akshare_symbol="sh000852",
        close_proxy_spec=AssetSpec(
            "H00852", "中证1000全收益", "csindex_tri", "H00852", True
        ),
    ),
    TimingAsset("guozheng2000", "国证2000", "sz399303"),
    TimingAsset("chinext", "创业板指", "sz399006"),
)


def resolve_timing_assets(raw: str) -> tuple[TimingAsset, ...]:
    if raw.strip().lower() == "all":
        return PAPER_ASSETS
    by_key = {asset.key.lower(): asset for asset in PAPER_ASSETS}
    by_code = {asset.akshare_symbol.lower(): asset for asset in PAPER_ASSETS}
    aliases = {
        "h00300": "large-cap",
        "000300": "large-cap",
        "h00905": "mid-cap",
        "000905": "mid-cap",
        "h00852": "small-cap",
        "000852": "small-cap",
        "399303": "guozheng2000",
        "399006": "chinext",
    }
    assets: list[TimingAsset] = []
    for part in raw.split(","):
        key = part.strip().lower()
        if not key:
            continue
        alias = aliases.get(key, key)
        asset = by_key.get(alias) or by_code.get(alias)
        if asset is None:
            available = ",".join(asset.key for asset in PAPER_ASSETS)
            raise TechnicalTimingError(
                f"Unknown technical-timing asset: {part}. Available: {available}"
            )
        assets.append(asset)
    return tuple(assets)


def load_timing_ohlcv(
    asset: TimingAsset,
    start_date: str,
    end_date: str,
    csv_dir: str | Path | None,
    data_source: TimingDataSource,
) -> pd.DataFrame:
    if csv_dir is not None:
        path = Path(csv_dir) / f"{asset.key}.csv"
        if path.exists():
            return _read_ohlcv_csv(path, start_date, end_date)
    match data_source:
        case "akshare-ohlcv":
            return _fetch_akshare_ohlcv(asset, start_date, end_date)
        case "close-proxy":
            return _fetch_close_proxy(asset, start_date, end_date)
        case unreachable:
            assert_never(unreachable)


def _fetch_akshare_ohlcv(
    asset: TimingAsset, start_date: str, end_date: str
) -> pd.DataFrame:
    raw = ak.stock_zh_index_daily(symbol=asset.akshare_symbol)
    raw["date"] = pd.to_datetime(raw["date"])
    frame = raw.set_index("date").sort_index()
    return _window_ohlcv(frame, start_date, end_date)


def _fetch_close_proxy(
    asset: TimingAsset, start_date: str, end_date: str
) -> pd.DataFrame:
    if asset.close_proxy_spec is None:
        raise TechnicalTimingError(
            f"{asset.key} has no close-proxy source; use --data-source akshare-ohlcv"
        )
    close = fetch_price_series(asset.close_proxy_spec, start_date, end_date)
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close),
            "high": close,
            "low": close,
            "close": close,
            "volume": 1.0,
        },
        index=close.index,
    )


def _read_ohlcv_csv(path: Path, start_date: str, end_date: str) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame = frame.rename(
        columns={
            "日期": "date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
        }
    )
    frame["date"] = pd.to_datetime(frame["date"])
    return _window_ohlcv(frame.set_index("date").sort_index(), start_date, end_date)


def _window_ohlcv(frame: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
    window = frame.loc[
        (frame.index >= pd.Timestamp(start_date))
        & (frame.index <= pd.Timestamp(end_date))
    ]
    result = window.loc[:, ["open", "high", "low", "close", "volume"]].copy()
    for column in result.columns:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return result.dropna(subset=["close"]).ffill()
