from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_build_dca_matrices_works_with_the_shared_annual_frame_contract() -> None:
    from investlab.scenarios.dca_matrix import build_dca_matrices

    annual = pd.DataFrame(
        {
            "date": pd.to_datetime(["2019-12-31", "2020-12-31", "2021-12-31"]),
            "close": [100.0, 110.0, 121.0],
        },
        index=pd.Index([2019, 2020, 2021]),
    )
    irr, terminal_values = build_dca_matrices(annual, 2020, 2021)
    assert float(irr.at[1, 2020]) == pytest.approx(10.0)
    assert float(terminal_values.at[2, 2020]) == pytest.approx(2.31)
