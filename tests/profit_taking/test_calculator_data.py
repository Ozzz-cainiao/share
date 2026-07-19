from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd  # noqa: PANDAS_OK
import pytest

from investlab.profit_taking.calculator_data import (
    CalculatorDataError,
    build_calculator_payload,
    write_calculator_payload,
)

RETRIEVED_AT = datetime(2026, 7, 19, 4, 5, 6, tzinfo=UTC)
CACHED_CHECKSUM = "383efc838c9b404c667d3e91a9f606e797ea55aa750faff626fe7c1b2fcf2e91"


def _canonical_bytes(prices: list[list[str | float]]) -> bytes:
    return "".join(
        f"{price_date},{format(float(close), '.17g')}\n" for price_date, close in prices
    ).encode()


def test_payload_normalizes_injected_rows_and_exposes_provenance() -> None:
    # Given: unsorted provider rows with a duplicate and invalid observations.
    raw = pd.DataFrame(
        {
            "日期": [
                "2020-01-03",
                "invalid",
                "2020-01-02",
                "2020-01-03",
                "2020-01-04",
            ],
            "收盘": [103, 999, 102, 104, -1],
        }
    )

    # When: the static payload is built twice from the injected loader.
    loader = lambda _symbol, _start, _end: raw  # noqa: E731
    first = build_calculator_payload(
        "H00300",
        date(2020, 1, 1),
        date(2020, 1, 5),
        loader=loader,
        retrieved_at_utc=RETRIEVED_AT,
    )
    second = build_calculator_payload(
        "H00300",
        date(2020, 1, 1),
        date(2020, 1, 5),
        loader=loader,
        retrieved_at_utc=RETRIEVED_AT,
    )
    payload = json.loads(first)

    # Then: serialization is deterministic and retains the canonical audit trail.
    assert first == second
    assert payload["schema_version"] == 1
    assert payload["asset"] == {
        "symbol": "H00300",
        "name": "沪深300全收益指数",
        "kind": "total_return_index",
    }
    assert payload["prices"] == [["2020-01-02", 102.0], ["2020-01-03", 104.0]]
    provenance = payload["provenance"]
    assert provenance["provider"].startswith("csindex_tri")
    assert provenance["retrieved_at_utc"] == "2026-07-19T04:05:06Z"
    assert provenance["requested_coverage"] == ["2020-01-01", "2020-01-05"]
    assert provenance["actual_coverage"] == ["2020-01-02", "2020-01-03"]
    assert provenance["source_row_count"] == 5
    assert provenance["normalized_row_count"] == 2
    assert provenance["duplicate_date_count"] == 1
    assert provenance["invalid_date_count"] == 1
    assert provenance["invalid_close_count"] == 1
    assert "duplicate_dates_last_value_wins" in provenance["cleaning_actions"]
    checksum = hashlib.sha256(_canonical_bytes(payload["prices"])).hexdigest()
    assert provenance["checksum_sha256"] == checksum


def test_cached_daily_csv_builds_the_characterized_1828_row_payload() -> None:
    # Given: the current local H00300 build cache, never treated as source truth.
    cache = Path("output/profit_taking_simple/daily.csv")

    # When: it is selected explicitly for an offline preview build.
    serialized = build_calculator_payload(
        "H00300",
        "2019-01-02",
        "2026-07-17",
        cached_price_csv=cache,
        expected_checksum_sha256=CACHED_CHECKSUM,
        retrieved_at_utc=RETRIEVED_AT,
    )
    payload = json.loads(serialized)

    # Then: characterized coverage and checksum remain exact.
    assert len(payload["prices"]) == 1_828
    assert payload["prices"][0][0] == "2019-01-02"
    assert payload["prices"][-1][0] == "2026-07-17"
    assert payload["provenance"]["checksum_sha256"] == CACHED_CHECKSUM
    assert (
        hashlib.sha256(_canonical_bytes(payload["prices"])).hexdigest()
        == CACHED_CHECKSUM
    )


@pytest.mark.parametrize(
    ("symbol", "raw", "message"),
    [
        ("H00905", pd.DataFrame({"日期": ["2020-01-02"], "收盘": [100]}), "H00300"),
        ("H00300", pd.DataFrame(), "empty"),
        (
            "H00300",
            pd.DataFrame({"wrong": ["2020-01-02"], "收盘": [100]}),
            "required columns",
        ),
    ],
)
def test_invalid_provider_input_fails_without_a_payload(
    symbol: str,
    raw: pd.DataFrame,
    message: str,
) -> None:
    # Given: a non-H00300 symbol, empty data, or malformed provider columns.
    # When/Then: the builder fails instead of returning partial JSON.
    with pytest.raises(CalculatorDataError, match=message):
        build_calculator_payload(
            symbol,
            "2020-01-01",
            "2020-01-03",
            loader=lambda _symbol, _start, _end: raw,
            retrieved_at_utc=RETRIEVED_AT,
        )


def test_stale_checksum_aborts_before_writing_output(tmp_path: Path) -> None:
    # Given: a destination and a checksum that no longer matches cached prices.
    destination = tmp_path / "site"

    # When/Then: validation aborts before creating any output.
    with pytest.raises(CalculatorDataError, match="checksum"):
        write_calculator_payload(
            destination,
            symbol="H00300",
            requested_start="2019-01-02",
            requested_end="2026-07-17",
            cached_price_csv=Path("output/profit_taking_simple/daily.csv"),
            expected_checksum_sha256="0" * 64,
            retrieved_at_utc=RETRIEVED_AT,
        )
    assert not destination.exists()


def test_malformed_cached_csv_aborts_without_partial_output(tmp_path: Path) -> None:
    # Given: an explicit cache with the wrong columns.
    cache = tmp_path / "bad.csv"
    cache.write_text("day,value\n2020-01-02,100\n", encoding="utf-8")
    destination = tmp_path / "site"

    # When/Then: parsing fails before the asset directory is created.
    with pytest.raises(CalculatorDataError, match="date and close"):
        write_calculator_payload(
            destination,
            symbol="H00300",
            requested_start="2020-01-01",
            requested_end="2020-01-03",
            cached_price_csv=cache,
            retrieved_at_utc=RETRIEVED_AT,
        )
    assert not destination.exists()


def test_directory_cache_error_is_translated_without_partial_output(
    tmp_path: Path,
) -> None:
    # Given: a directory where an explicit cached CSV file is required.
    cache = tmp_path / "cache"
    cache.mkdir()
    destination = tmp_path / "site"

    # When/Then: the I/O failure becomes a domain error before site creation.
    with pytest.raises(CalculatorDataError, match="could not be read"):
        write_calculator_payload(
            destination,
            symbol="H00300",
            requested_start="2020-01-01",
            requested_end="2020-01-03",
            cached_price_csv=cache,
            retrieved_at_utc=RETRIEVED_AT,
        )
    assert not destination.exists()


def test_writer_returns_the_relative_static_asset_path(tmp_path: Path) -> None:
    # Given: a valid injected build source and the default relative asset contract.
    output_dir = tmp_path / "site"
    raw = pd.DataFrame({"日期": ["2020-01-02", "2020-01-03"], "收盘": [100, 101]})

    # When: the validated payload is written.
    written = write_calculator_payload(
        output_dir,
        symbol="H00300",
        requested_start="2020-01-01",
        requested_end="2020-01-03",
        loader=lambda _symbol, _start, _end: raw,
        retrieved_at_utc=RETRIEVED_AT,
    )

    # Then: the returned asset remains portable relative to the site root.
    assert written.relative_to(output_dir).as_posix() == "assets/h00300-prices.json"
    assert json.loads(written.read_text(encoding="utf-8"))["prices"][-1][0] == (
        "2020-01-03"
    )


@pytest.mark.parametrize("asset_path", ["/prices.json", "../prices.json", ""])
def test_asset_path_must_remain_relative_and_inside_site(
    tmp_path: Path,
    asset_path: str,
) -> None:
    # Given: an absolute, escaping, or empty asset path.
    # When/Then: the writer rejects it before touching the site.
    with pytest.raises(CalculatorDataError, match="relative asset"):
        write_calculator_payload(
            tmp_path / "site",
            symbol="H00300",
            requested_start="2020-01-01",
            requested_end="2020-01-03",
            asset_path=asset_path,
            loader=lambda _symbol, _start, _end: pd.DataFrame(
                {"日期": ["2020-01-02", "2020-01-03"], "收盘": [100, 101]}
            ),
            retrieved_at_utc=RETRIEVED_AT,
        )


def test_asset_symlink_cannot_escape_the_resolved_site_root(tmp_path: Path) -> None:
    # Given: a site asset directory symlinked to a location outside the site.
    output_dir = tmp_path / "site"
    outside = tmp_path / "outside"
    output_dir.mkdir()
    outside.mkdir()
    (output_dir / "assets").symlink_to(outside, target_is_directory=True)
    raw = pd.DataFrame({"日期": ["2020-01-02", "2020-01-03"], "收盘": [100, 101]})

    # When/Then: resolved containment fails without writing through the symlink.
    with pytest.raises(CalculatorDataError, match="resolved site root"):
        write_calculator_payload(
            output_dir,
            symbol="H00300",
            requested_start="2020-01-01",
            requested_end="2020-01-03",
            loader=lambda _symbol, _start, _end: raw,
            retrieved_at_utc=RETRIEVED_AT,
        )
    assert not (outside / "h00300-prices.json").exists()
