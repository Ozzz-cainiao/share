from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Final

import pandas as pd
import requests


@dataclass(frozen=True, slots=True)
class NormalizePriceFrameInput:
    date_column: str
    close_column: str
    series_name: str
    start_date: str | pd.Timestamp | None = None
    end_date: str | pd.Timestamp | None = None


_CACHE_DIR: Final[Path] = (
    Path(__file__).resolve().parents[2] / "output" / ".cache"
)


def _normalize_bound(bound: str | pd.Timestamp | None) -> pd.Timestamp | None:
    if bound is None:
        return None
    return pd.Timestamp(bound)


def normalize_price_frame(
    frame: pd.DataFrame, config: NormalizePriceFrameInput
) -> pd.Series:
    dates = pd.to_datetime(frame[config.date_column], errors="coerce")
    values = pd.to_numeric(frame[config.close_column], errors="coerce")
    series = pd.Series(values.to_numpy(), index=dates, name=config.series_name)
    series = series[~series.index.isna()].dropna().sort_index()
    series = series[~series.index.duplicated(keep="last")]
    series = series[series > 0]

    start_date = _normalize_bound(config.start_date)
    end_date = _normalize_bound(config.end_date)
    if start_date is not None:
        series = series.loc[series.index >= start_date]
    if end_date is not None:
        series = series.loc[series.index <= end_date]
    return series


def _fred_csv_text(series_id: str, timeout: int = 60) -> str:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        from curl_cffi import requests as curl_requests

        response = curl_requests.get(url, timeout=timeout, impersonate="chrome")
        response.raise_for_status()
        return response.content.decode("utf-8")
    except Exception:
        response = requests.get(
            url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout
        )
        response.raise_for_status()
        return response.content.decode("utf-8")


def fetch_fred_closes(series_id: str, start_year: int, end_year: int) -> pd.Series:
    raw = pd.read_csv(StringIO(_fred_csv_text(series_id)))
    if raw is None or raw.empty or series_id not in raw.columns:
        raise RuntimeError(f"FRED 未返回 {series_id} 的数据")

    closes = normalize_price_frame(
        raw,
        NormalizePriceFrameInput(
            date_column="observation_date",
            close_column=series_id,
            series_name=series_id,
            start_date=f"{start_year - 1}-01-01",
            end_date=f"{end_year}-12-31",
        ),
    )
    if closes.empty:
        raise RuntimeError(f"{series_id} 在 {start_year - 1}–{end_year} 没有可用的正数收盘价")
    return closes


def _yahoo_cache_path(symbol: str) -> Path:
    safe_symbol = symbol.replace("/", "_")
    return _CACHE_DIR / f"yahoo_{safe_symbol}_daily.csv"


def fetch_yahoo_index_closes(
    symbol: str, start_year: int, end_year: int
) -> pd.Series:
    cache_path = _yahoo_cache_path(symbol)
    frame: pd.DataFrame | None = None
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        raw = ticker.history(period="max", auto_adjust=False)
        if raw is not None and not raw.empty:
            close_column = "Close" if "Close" in raw.columns else str(raw.columns[0])
            frame = pd.DataFrame(
                {
                    "date": pd.to_datetime(raw.index),
                    "close": pd.to_numeric(raw[close_column], errors="coerce"),
                }
            ).dropna(subset=["close"])
    except Exception:
        frame = None

    if frame is None or frame.empty:
        if cache_path.exists():
            frame = pd.read_csv(cache_path, parse_dates=["date"])
        else:
            raise RuntimeError(
                f"yfinance 取 {symbol} 失败（可能被限速）且无本地缓存：{cache_path}"
            )
    else:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        frame = frame.sort_values("date")
        frame.to_csv(cache_path, index=False, encoding="utf-8")

    closes = normalize_price_frame(
        frame,
        NormalizePriceFrameInput(
            date_column="date",
            close_column="close",
            series_name=symbol,
            start_date=f"{start_year - 1}-01-01",
            end_date=f"{end_year}-12-31",
        ),
    )
    if closes.empty:
        raise RuntimeError(f"{symbol} 在 {start_year - 1}–{end_year} 没有可用的正数收盘价")
    return closes
