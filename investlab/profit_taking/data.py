from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Final

import pandas as pd  # noqa: PANDAS_OK

from investlab.data import fetch_price_series, select_assets

H00300_SYMBOL: Final = "H00300"
H00300_PROVIDER: Final = "csindex_tri (AkShare stock_zh_index_hist_csindex)"
_DATE_COLUMN: Final = "日期"
_CLOSE_COLUMN: Final = "收盘"
_CLEANING_ACTIONS: Final = (
    "dates_sorted_ascending",
    "duplicate_dates_last_value_wins",
    "invalid_dates_dropped",
    "missing_nonfinite_nonpositive_closes_dropped",
    "missing_observations_not_forward_filled",
    "annual_1.026_adjustment_bypassed",
)

RawH00300Loader = Callable[[str, date, date], pd.DataFrame]


@dataclass(frozen=True, slots=True)
class DataProvenance:
    provider: str
    retrieved_at_utc: datetime
    requested_start: date
    requested_end: date
    actual_start: date
    actual_end: date
    source_row_count: int
    normalized_row_count: int
    duplicate_date_count: int
    invalid_date_count: int
    missing_close_count: int
    invalid_close_count: int
    cleaning_actions: tuple[str, ...]
    checksum_sha256: str


@dataclass(frozen=True, slots=True)
class H00300DataError(ValueError):
    reason: str

    def __str__(self) -> str:
        return self.reason


@dataclass(frozen=True, slots=True)
class _NormalizedPrices:
    prices: pd.Series
    source_row_count: int
    duplicate_date_count: int
    invalid_date_count: int
    missing_close_count: int
    invalid_close_count: int


def _parse_requested_date(value: date | str, label: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise H00300DataError(f"{label} must be an ISO YYYY-MM-DD date") from exc


def _default_raw_loader(symbol: str, start: date, end: date) -> pd.DataFrame:
    spec = select_assets([symbol])[0]
    prices = fetch_price_series(spec, start.isoformat(), end.isoformat())
    return pd.DataFrame({_DATE_COLUMN: prices.index, _CLOSE_COLUMN: prices.to_numpy()})


def _normalize_raw_frame(
    raw: pd.DataFrame,
    requested_start: date,
    requested_end: date,
) -> _NormalizedPrices:
    if raw.empty:
        raise H00300DataError("provider returned an empty H00300 frame")
    missing_columns = {_DATE_COLUMN, _CLOSE_COLUMN} - set(raw.columns)
    if missing_columns:
        raise H00300DataError(
            "provider frame is missing required columns: 日期 and 收盘"
        )

    dates = pd.to_datetime(raw[_DATE_COLUMN], errors="coerce")
    closes = pd.to_numeric(raw[_CLOSE_COLUMN], errors="coerce")
    invalid_dates = dates.isna()
    missing_closes = closes.isna()
    finite_closes = closes.map(
        lambda value: math.isfinite(float(value)) if pd.notna(value) else False
    )
    invalid_closes = (~missing_closes) & ((~finite_closes) | (closes <= 0))

    frame = pd.DataFrame({"date": dates, "close": closes})
    frame = frame.loc[~invalid_dates].sort_values("date", kind="stable")
    duplicate_count = int(frame.duplicated("date", keep="last").sum())
    frame = frame.drop_duplicates("date", keep="last")
    valid_close = frame["close"].notna() & frame["close"].map(
        lambda value: math.isfinite(float(value)) and float(value) > 0
    )
    frame = frame.loc[valid_close]
    requested_start_timestamp = pd.Timestamp(requested_start)
    requested_end_timestamp = pd.Timestamp(requested_end)
    frame = frame.loc[
        (frame["date"] >= requested_start_timestamp)
        & (frame["date"] <= requested_end_timestamp)
    ]
    prices = pd.Series(
        frame["close"].astype(float).to_numpy(),
        index=pd.DatetimeIndex(frame["date"].to_numpy(), name=None),
        name=H00300_SYMBOL,
    )
    if prices.empty:
        raise H00300DataError(
            "normalization found no positive finite H00300 closes in requested coverage"
        )
    if len(prices) < 2:
        raise H00300DataError(
            "requested coverage contains fewer than two normalized observations"
        )
    return _NormalizedPrices(
        prices=prices,
        source_row_count=len(raw),
        duplicate_date_count=duplicate_count,
        invalid_date_count=int(invalid_dates.sum()),
        missing_close_count=int(missing_closes.sum()),
        invalid_close_count=int(invalid_closes.sum()),
    )


def canonical_price_bytes(prices: pd.Series) -> bytes:
    """Serialize normalized closes for a deterministic full SHA-256 checksum."""
    rows = (
        f"{timestamp.date().isoformat()},{format(float(close), '.17g')}\n"
        for timestamp, close in prices.items()
    )
    return "".join(rows).encode("utf-8")


def load_h00300_prices(
    symbol: str,
    requested_start: date | str,
    requested_end: date | str,
    *,
    loader: RawH00300Loader | None = None,
    retrieved_at_utc: datetime | None = None,
) -> tuple[pd.Series, DataProvenance]:
    """Load only raw H00300 total-return closes and return auditable provenance."""
    if symbol.upper() != H00300_SYMBOL:
        raise H00300DataError(
            f"unsupported symbol {symbol!r}; this loader resolves only H00300"
        )
    start = _parse_requested_date(requested_start, "requested_start")
    end = _parse_requested_date(requested_end, "requested_end")
    if start > end:
        raise H00300DataError("requested coverage start must not follow end")
    retrieved_at = retrieved_at_utc or datetime.now(UTC)
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() != UTC.utcoffset(None):
        raise H00300DataError("retrieved_at_utc must be timezone-aware UTC")

    normalized = _normalize_raw_frame(
        (loader or _default_raw_loader)(H00300_SYMBOL, start, end),
        start,
        end,
    )
    checksum = hashlib.sha256(canonical_price_bytes(normalized.prices)).hexdigest()
    provenance = DataProvenance(
        provider=H00300_PROVIDER,
        retrieved_at_utc=retrieved_at,
        requested_start=start,
        requested_end=end,
        actual_start=normalized.prices.index[0].date(),
        actual_end=normalized.prices.index[-1].date(),
        source_row_count=normalized.source_row_count,
        normalized_row_count=len(normalized.prices),
        duplicate_date_count=normalized.duplicate_date_count,
        invalid_date_count=normalized.invalid_date_count,
        missing_close_count=normalized.missing_close_count,
        invalid_close_count=normalized.invalid_close_count,
        cleaning_actions=_CLEANING_ACTIONS,
        checksum_sha256=checksum,
    )
    return normalized.prices, provenance
