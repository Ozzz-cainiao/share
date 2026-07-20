from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd  # noqa: PANDAS_OK
import pytest

from investlab.profit_taking.data import (
    H00300DataError,
    canonical_price_bytes,
    load_h00300_prices,
)


RETRIEVED_AT = datetime(2026, 7, 19, 3, 4, 5, tzinfo=UTC)


def test_load_h00300_prices_normalizes_dirty_rows_deterministically() -> None:
    # Given
    dirty = pd.DataFrame(
        {
            "日期": [
                "2020-01-03",
                "bad-date",
                "2020-01-02",
                "2020-01-03",
                "2020-01-04",
                "2020-01-05",
                "2020-01-06",
            ],
            "收盘": [103.0, 99.0, 102.0, 104.0, float("nan"), 0.0, float("inf")],
        }
    )

    def loader(symbol: str, start: date, end: date) -> pd.DataFrame:
        assert (symbol, start, end) == (
            "H00300",
            date(2020, 1, 2),
            date(2020, 1, 3),
        )
        return dirty

    # When
    prices, provenance = load_h00300_prices(
        "H00300",
        date(2020, 1, 2),
        date(2020, 1, 3),
        loader=loader,
        retrieved_at_utc=RETRIEVED_AT,
    )

    # Then
    expected = pd.Series(
        [102.0, 104.0],
        index=pd.DatetimeIndex(["2020-01-02", "2020-01-03"]),
        name="H00300",
    )
    pd.testing.assert_series_equal(prices, expected, check_freq=False)
    assert provenance.source_row_count == 7
    assert provenance.normalized_row_count == 2
    assert provenance.duplicate_date_count == 1
    assert provenance.invalid_date_count == 1
    assert provenance.missing_close_count == 1
    assert provenance.invalid_close_count == 2
    assert provenance.actual_start == date(2020, 1, 2)
    assert provenance.actual_end == date(2020, 1, 3)
    assert provenance.retrieved_at_utc == RETRIEVED_AT
    assert "duplicate_dates_last_value_wins" in provenance.cleaning_actions
    assert "missing_observations_not_forward_filled" in provenance.cleaning_actions
    assert "annual_1.026_adjustment_bypassed" in provenance.cleaning_actions


def test_canonical_checksum_is_stable_for_shuffled_duplicate_input() -> None:
    # Given
    first = pd.DataFrame(
        {
            "日期": ["2020-01-03", "2020-01-02", "2020-01-03"],
            "收盘": [103.0, 102.0, 104.0],
        }
    )
    second = first.iloc[[1, 0, 2]].reset_index(drop=True)

    def first_loader(_symbol: str, _start: date, _end: date) -> pd.DataFrame:
        return first

    def second_loader(_symbol: str, _start: date, _end: date) -> pd.DataFrame:
        return second

    # When
    prices_a, provenance_a = load_h00300_prices(
        "H00300",
        date(2020, 1, 2),
        date(2020, 1, 3),
        loader=first_loader,
        retrieved_at_utc=RETRIEVED_AT,
    )
    prices_b, provenance_b = load_h00300_prices(
        "H00300",
        date(2020, 1, 2),
        date(2020, 1, 3),
        loader=second_loader,
        retrieved_at_utc=RETRIEVED_AT,
    )

    # Then
    pd.testing.assert_series_equal(prices_a, prices_b)
    assert provenance_a.checksum_sha256 == provenance_b.checksum_sha256
    payload = b"2020-01-02,102\n2020-01-03,104\n"
    assert canonical_price_bytes(prices_a) == payload
    assert provenance_a.checksum_sha256 == hashlib.sha256(payload).hexdigest()


def test_checksum_is_recomputed_without_stale_state() -> None:
    # Given
    current = {"close": 101.0}

    def loader(_symbol: str, _start: date, _end: date) -> pd.DataFrame:
        return pd.DataFrame(
            {"日期": ["2020-01-02", "2020-01-03"], "收盘": [100.0, current["close"]]}
        )

    # When
    _, first = load_h00300_prices(
        "H00300",
        date(2020, 1, 2),
        date(2020, 1, 3),
        loader=loader,
        retrieved_at_utc=RETRIEVED_AT,
    )
    current["close"] = 102.0
    _, second = load_h00300_prices(
        "H00300",
        date(2020, 1, 2),
        date(2020, 1, 3),
        loader=loader,
        retrieved_at_utc=RETRIEVED_AT,
    )

    # Then
    assert first.checksum_sha256 != second.checksum_sha256


def test_load_h00300_prices_does_not_forward_fill_missing_sessions() -> None:
    # Given
    def loader(_symbol: str, _start: date, _end: date) -> pd.DataFrame:
        return pd.DataFrame(
            {"日期": ["2020-01-02", "2020-01-06"], "收盘": [100.0, 101.0]}
        )

    # When
    prices, _ = load_h00300_prices(
        "H00300",
        date(2020, 1, 2),
        date(2020, 1, 6),
        loader=loader,
        retrieved_at_utc=RETRIEVED_AT,
    )

    # Then
    assert prices.index.tolist() == [
        pd.Timestamp("2020-01-02"),
        pd.Timestamp("2020-01-06"),
    ]


def test_load_h00300_prices_drops_duplicate_weekend_requested_boundary() -> None:
    # Given: the provider repeats the first tradable close on a requested Sunday.
    def loader(_symbol: str, _start: date, _end: date) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "日期": ["2006-01-01", "2006-01-04", "2006-01-05"],
                "收盘": [941.43, 941.43, 959.13],
            }
        )

    # When: the requested interval begins on that non-trading boundary.
    prices, provenance = load_h00300_prices(
        "H00300",
        date(2006, 1, 1),
        date(2006, 1, 5),
        loader=loader,
        retrieved_at_utc=RETRIEVED_AT,
    )

    # Then: the synthetic Sunday cannot become a contribution session.
    assert prices.index.tolist() == [
        pd.Timestamp("2006-01-04"),
        pd.Timestamp("2006-01-05"),
    ]
    assert provenance.requested_start == date(2006, 1, 1)
    assert provenance.actual_start == date(2006, 1, 4)
    assert (
        "synthetic_nontrading_requested_boundary_dropped" in provenance.cleaning_actions
    )


def test_load_h00300_prices_drops_all_weekend_rows() -> None:
    def loader(_symbol: str, _start: date, _end: date) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "日期": ["2020-01-03", "2020-01-04", "2020-01-05", "2020-01-06"],
                "收盘": [100.0, 100.0, 100.0, 101.0],
            }
        )

    prices, _ = load_h00300_prices(
        "H00300",
        date(2020, 1, 3),
        date(2020, 1, 6),
        loader=loader,
        retrieved_at_utc=RETRIEVED_AT,
    )

    assert prices.index.tolist() == [
        pd.Timestamp("2020-01-03"),
        pd.Timestamp("2020-01-06"),
    ]


@pytest.mark.parametrize(
    ("symbol", "frame", "message"),
    [
        ("H00905", pd.DataFrame({"日期": ["2020-01-02"], "收盘": [100]}), "H00300"),
        ("H00300", pd.DataFrame(), "empty"),
        (
            "H00300",
            pd.DataFrame({"日期": ["2020-01-02"], "收盘": [0]}),
            "positive finite",
        ),
        (
            "H00300",
            pd.DataFrame({"日期": ["2020-01-02"], "wrong": [100]}),
            "required columns",
        ),
    ],
)
def test_load_h00300_prices_rejects_malformed_or_unsupported_data(
    symbol: str,
    frame: pd.DataFrame,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Given
    calls = 0
    monkeypatch.chdir(tmp_path)

    def loader(_symbol: str, _start: date, _end: date) -> pd.DataFrame:
        nonlocal calls
        calls += 1
        return frame

    # When / Then
    with pytest.raises(H00300DataError, match=message):
        load_h00300_prices(
            symbol,
            date(2020, 1, 2),
            date(2020, 1, 3),
            loader=loader,
            retrieved_at_utc=RETRIEVED_AT,
        )
    if symbol != "H00300":
        assert calls == 0
    assert list(tmp_path.iterdir()) == []


def test_load_h00300_prices_rejects_insufficient_requested_coverage() -> None:
    # Given
    def loader(_symbol: str, _start: date, _end: date) -> pd.DataFrame:
        return pd.DataFrame({"日期": ["2020-01-03"], "收盘": [100.0]})

    # When / Then
    with pytest.raises(H00300DataError, match="coverage"):
        load_h00300_prices(
            "H00300",
            date(2020, 1, 2),
            date(2020, 1, 3),
            loader=loader,
            retrieved_at_utc=RETRIEVED_AT,
        )


def test_load_h00300_prices_rejects_non_utc_retrieval_time() -> None:
    # Given
    def loader(_symbol: str, _start: date, _end: date) -> pd.DataFrame:
        return pd.DataFrame(
            {"日期": ["2020-01-02", "2020-01-03"], "收盘": [100.0, 101.0]}
        )

    # When / Then
    with pytest.raises(H00300DataError, match="UTC"):
        load_h00300_prices(
            "H00300",
            date(2020, 1, 2),
            date(2020, 1, 3),
            loader=loader,
            retrieved_at_utc=datetime(2026, 7, 19, 3, 4, 5),
        )
