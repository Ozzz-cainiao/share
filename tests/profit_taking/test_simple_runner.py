from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd  # noqa: PANDAS_OK

from investlab.profit_taking.simple_runner import generate_simple_result


def test_generate_simple_result_writes_html_and_audit_files(tmp_path: Path) -> None:
    # Given: an offline H00300 provider fixture with one exact 20% cycle.
    def loader(symbol: str, start: date, end: date) -> pd.DataFrame:
        assert symbol == "H00300"
        assert start == date(2019, 1, 1)
        assert end == date(2019, 2, 1)
        return pd.DataFrame(
            {
                "日期": ["2019-01-02", "2019-02-01"],
                "收盘": [100.0, 120.0],
            }
        )

    # When: the public result generator runs through data, engine, and renderer.
    result, report_path = generate_simple_result(
        tmp_path,
        date(2019, 2, 1),
        loader,
    )

    # Then: the observable report and audit artifacts are complete.
    assert result.summary.profit_take_count == 1
    assert report_path == tmp_path / "index.html"
    assert report_path.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert (tmp_path / "summary.json").exists()
    assert (tmp_path / "profit_takes.csv").exists()
    assert (tmp_path / "daily.csv").exists()
