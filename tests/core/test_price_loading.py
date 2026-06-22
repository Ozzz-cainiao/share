from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from investlab.models import AssetSpec


def test_fetch_price_series_characterizes_current_csindex_normalization_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from investlab import data

    raw = pd.DataFrame(
        {
            "日期": ["2020-01-03", "2020-01-02", "2020-01-03", "2020-01-04", "2020-01-05"],
            "收盘": [1.0, 2.0, 3.0, 0.0, None],
        }
    )
    spec = AssetSpec("H00300", "沪深300全收益", "csindex_tri", "H00300")
    monkeypatch.setattr(data.ak, "stock_zh_index_hist_csindex", lambda **_: raw)
    series = data.fetch_price_series(spec, "2020-01-01", "2020-12-31")
    expected = pd.Series(
        [2.0, 3.0],
        index=pd.to_datetime(["2020-01-02", "2020-01-03"]),
        name="H00300",
    )
    expected.index.name = "日期"
    pd.testing.assert_series_equal(series, expected)


def test_shared_price_normalizer_matches_the_characterized_csindex_behavior() -> None:
    from investlab.core.price_loading import NormalizePriceFrameInput, normalize_price_frame

    raw = pd.DataFrame(
        {
            "日期": ["2020-01-03", "2020-01-02", "2020-01-03", "2020-01-04", "2020-01-05"],
            "收盘": [1.0, 2.0, 3.0, 0.0, None],
        }
    )
    series = normalize_price_frame(
        raw,
        NormalizePriceFrameInput(
            date_column="日期",
            close_column="收盘",
            series_name="H00300",
        ),
    )
    expected = pd.Series(
        [2.0, 3.0],
        index=pd.to_datetime(["2020-01-02", "2020-01-03"]),
        name="H00300",
    )
    expected.index.name = "日期"
    pd.testing.assert_series_equal(series, expected)


def test_fetch_fred_closes_characterizes_us_asset_normalization_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from investlab.core import price_loading

    synthetic_csv = (
        "observation_date,XNDX\n"
        "2020-01-02,9000.0\n"
        "2020-01-03,9100.0\n"
        "2020-12-31,12000.0\n"
        "2021-01-04,11900.0\n"
    )
    monkeypatch.setattr(
        price_loading, "_fred_csv_text", lambda series_id, timeout=60: synthetic_csv
    )

    closes = price_loading.fetch_fred_closes("XNDX", 2020, 2021)
    expected = pd.Series(
        [9000.0, 9100.0, 12000.0, 11900.0],
        index=pd.to_datetime(["2020-01-02", "2020-01-03", "2020-12-31", "2021-01-04"]),
        name="XNDX",
    )
    expected.index.name = "observation_date"
    pd.testing.assert_series_equal(closes, expected)
