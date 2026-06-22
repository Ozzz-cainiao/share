from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_shared_annual_close_helper_characterizes_year_end_behavior() -> None:
    from investlab.scenarios.annual_matrix import year_end_closes

    closes = pd.Series(
        [100.0, 110.0, 120.0, 130.0],
        index=pd.to_datetime(["2019-12-30", "2019-12-31", "2020-12-30", "2020-12-31"]),
        name="demo",
    )
    annual = year_end_closes(closes)
    expected = pd.DataFrame(
        {
            "date": pd.to_datetime(["2019-12-31", "2020-12-31"]),
            "close": [110.0, 130.0],
        },
        index=pd.Index([2019, 2020], dtype="int32"),
    )
    pd.testing.assert_frame_equal(annual, expected)


def test_shared_adjustment_helper_preserves_the_documented_h00300_fix() -> None:
    from investlab.scenarios.annual_matrix import apply_known_adjustments

    annual = pd.DataFrame(
        {
            "date": pd.to_datetime(["2004-12-31", "2005-12-30", "2006-12-29"]),
            "close": [100.0, 90.0, 120.0],
        },
        index=pd.Index([2004, 2005, 2006]),
    )
    adjusted, notes = apply_known_adjustments(annual, "H00300")
    expected = annual.copy()
    expected.loc[expected.index >= 2005, "close"] *= 1.026
    pd.testing.assert_frame_equal(adjusted, expected)
    assert notes == [
        "H00300 已应用2005年分红估算修正：2005年及以后财富指数乘以1.026，2005年收益由-7.65%修正为约-5.25%"
    ]
