from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import Final, TypedDict

import pandas as pd  # noqa: PANDAS_OK

from investlab.profit_taking.data import (
    H00300_SYMBOL,
    DataProvenance,
    H00300DataError,
    RawH00300Loader,
    canonical_price_bytes,
    load_h00300_prices,
)

_SCHEMA_VERSION: Final = 1
_DEFAULT_ASSET_PATH: Final = "assets/h00300-prices.json"
_ASSET_NAME: Final = "沪深300全收益指数"
_ASSET_KIND: Final = "total_return_index"


@dataclass(frozen=True, slots=True)
class CalculatorDataError(ValueError):
    reason: str

    def __str__(self) -> str:
        return self.reason


class _ProvenancePayload(TypedDict):
    actual_coverage: list[str]
    checksum_sha256: str
    cleaning_actions: list[str]
    duplicate_date_count: int
    invalid_close_count: int
    invalid_date_count: int
    missing_close_count: int
    normalized_row_count: int
    provider: str
    requested_coverage: list[str]
    retrieved_at_utc: str
    source_row_count: int


def build_calculator_payload(
    symbol: str,
    requested_start: date | str,
    requested_end: date | str,
    *,
    loader: RawH00300Loader | None = None,
    cached_price_csv: Path | None = None,
    expected_checksum_sha256: str | None = None,
    retrieved_at_utc: datetime | None = None,
) -> str:
    if loader is not None and cached_price_csv is not None:
        raise CalculatorDataError(
            "loader and cached_price_csv are mutually exclusive build inputs"
        )
    selected_loader = loader
    if cached_price_csv is not None:
        selected_loader = _cached_csv_loader(cached_price_csv)
    try:
        prices, provenance = load_h00300_prices(
            symbol,
            requested_start,
            requested_end,
            loader=selected_loader,
            retrieved_at_utc=retrieved_at_utc,
        )
    except H00300DataError as error:
        raise CalculatorDataError(str(error)) from error

    _require_expected_checksum(
        provenance.checksum_sha256,
        expected_checksum_sha256,
    )
    pairs = [
        [timestamp.date().isoformat(), float(close)]
        for timestamp, close in prices.items()
    ]
    emitted_checksum = hashlib.sha256(canonical_price_bytes(prices)).hexdigest()
    if emitted_checksum != provenance.checksum_sha256:
        raise CalculatorDataError("emitted prices do not match provenance checksum")

    payload = {
        "schema_version": _SCHEMA_VERSION,
        "asset": {
            "kind": _ASSET_KIND,
            "name": _ASSET_NAME,
            "symbol": H00300_SYMBOL,
        },
        "prices": pairs,
        "provenance": _provenance_payload(provenance),
    }
    return (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def write_calculator_payload(
    output_dir: Path,
    *,
    symbol: str,
    requested_start: date | str,
    requested_end: date | str,
    asset_path: str = _DEFAULT_ASSET_PATH,
    loader: RawH00300Loader | None = None,
    cached_price_csv: Path | None = None,
    expected_checksum_sha256: str | None = None,
    retrieved_at_utc: datetime | None = None,
) -> Path:
    relative_path = _parse_asset_path(asset_path)
    payload = build_calculator_payload(
        symbol,
        requested_start,
        requested_end,
        loader=loader,
        cached_price_csv=cached_price_csv,
        expected_checksum_sha256=expected_checksum_sha256,
        retrieved_at_utc=retrieved_at_utc,
    )
    destination = _resolved_destination(output_dir, relative_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(payload, encoding="utf-8")
    return destination


def _cached_csv_loader(path: Path) -> RawH00300Loader:
    def load(_symbol: str, _start: date, _end: date) -> pd.DataFrame:
        try:
            frame = pd.read_csv(path, encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError, pd.errors.ParserError) as error:
            raise CalculatorDataError(
                f"cached price CSV could not be read: {path}"
            ) from error
        if not {"date", "close"}.issubset(frame.columns):
            raise CalculatorDataError(
                "cached price CSV must contain date and close columns"
            )
        return frame.loc[:, ["date", "close"]].rename(
            columns={"date": "日期", "close": "收盘"}
        )

    return load


def _require_expected_checksum(actual: str, expected: str | None) -> None:
    if expected is not None and actual != expected.lower():
        raise CalculatorDataError(
            f"checksum mismatch: expected {expected.lower()}, calculated {actual}"
        )


def _parse_asset_path(asset_path: str) -> PurePosixPath:
    path = PurePosixPath(asset_path)
    if (
        not asset_path
        or "\\" in asset_path
        or path.is_absolute()
        or ".." in path.parts
        or path.name in {"", ".", ".."}
    ):
        raise CalculatorDataError(
            "asset_path must be a non-empty relative asset inside the site"
        )
    return path


def _resolved_destination(
    output_dir: Path,
    relative_path: PurePosixPath,
) -> Path:
    resolved_root = output_dir.resolve()
    destination = output_dir.joinpath(*relative_path.parts)
    resolved_parent = destination.parent.resolve()
    resolved_destination = destination.resolve()
    if not (
        resolved_parent.is_relative_to(resolved_root)
        and resolved_destination.is_relative_to(resolved_root)
    ):
        raise CalculatorDataError(
            "asset_path must remain inside the resolved site root"
        )
    return resolved_destination


def _provenance_payload(provenance: DataProvenance) -> _ProvenancePayload:
    retrieved_at = provenance.retrieved_at_utc.isoformat().replace("+00:00", "Z")
    return {
        "actual_coverage": [
            provenance.actual_start.isoformat(),
            provenance.actual_end.isoformat(),
        ],
        "checksum_sha256": provenance.checksum_sha256,
        "cleaning_actions": list(provenance.cleaning_actions),
        "duplicate_date_count": provenance.duplicate_date_count,
        "invalid_close_count": provenance.invalid_close_count,
        "invalid_date_count": provenance.invalid_date_count,
        "missing_close_count": provenance.missing_close_count,
        "normalized_row_count": provenance.normalized_row_count,
        "provider": provenance.provider,
        "requested_coverage": [
            provenance.requested_start.isoformat(),
            provenance.requested_end.isoformat(),
        ],
        "retrieved_at_utc": retrieved_at,
        "source_row_count": provenance.source_row_count,
    }
