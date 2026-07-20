from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
import pandas as pd  # noqa: PANDAS_OK

matplotlib.use("Agg")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def _sample_ohlcv() -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=90, freq="D")
    close = pd.Series(
        [110 - i * 0.3 for i in range(25)]
        + [102.5 + i * 0.8 for i in range(35)]
        + [130.5 - i * 0.7 for i in range(30)],
        index=dates,
        dtype=float,
    )
    return pd.DataFrame(
        {
            "open": close.shift(1).fillna(close.iloc[0]),
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 1000.0,
        },
        index=dates,
    )


def test_sma_default_signal_changes_exposure_on_trend_reversal() -> None:
    from investlab.technical_timing.catalog import default_indicator_specs
    from investlab.technical_timing.indicators import build_indicator_signals

    signals = build_indicator_signals(_sample_ohlcv(), default_indicator_specs())

    assert "SMA" in signals
    assert signals["SMA"].buy.sum() > 0
    assert signals["SMA"].sell.sum() > 0


def test_backtest_summary_contains_paper_metrics_for_default_indicators() -> None:
    from investlab.technical_timing.catalog import default_indicator_specs
    from investlab.technical_timing.engine import summarize_indicator_backtests
    from investlab.technical_timing.indicators import build_indicator_signals

    panel = _sample_ohlcv()
    signals = build_indicator_signals(panel, default_indicator_specs())
    summary = summarize_indicator_backtests(panel["close"], signals, fee_rate=0.0003)

    assert {
        "indicator",
        "category",
        "annual_return",
        "annual_excess",
        "max_drawdown",
    }.issubset(summary.columns)
    assert set(summary["indicator"]).issuperset({"SMA", "MACD", "RSI", "BBANDS", "OBV"})


def test_technical_timing_scenario_writes_summary_and_signal_files(
    monkeypatch, tmp_path
) -> None:
    from investlab.scenarios import technical_timing_scenario
    from investlab.technical_timing import scenario_core

    monkeypatch.setattr(
        scenario_core,
        "load_ohlcv_for_asset",
        lambda asset, start_date, end_date, csv_dir, data_source: _sample_ohlcv(),
    )

    args = argparse.Namespace(
        start_date="2020-01-01",
        end_date="2020-03-30",
        assets="large-cap",
        csv_dir=None,
        data_source="akshare-ohlcv",
        output_dir=tmp_path,
        fee_rate=0.0003,
    )

    assert technical_timing_scenario.run(args) == 0
    assert (tmp_path / "large-cap_ohlcv.csv").exists()
    assert (tmp_path / "large-cap_summary.csv").exists()
    assert (tmp_path / "large-cap_equity_curves.csv").exists()
    assert (tmp_path / "large-cap_equity_all.png").exists()
    assert (tmp_path / "large-cap_equity_trend.png").exists()
    assert (tmp_path / "large-cap_signals.csv").exists()


def test_equity_curves_frame_contains_benchmark_and_indicator_curves() -> None:
    from investlab.technical_timing.catalog import default_indicator_specs
    from investlab.technical_timing.engine import equity_curves_frame
    from investlab.technical_timing.indicators import build_indicator_signals

    panel = _sample_ohlcv()
    signals = build_indicator_signals(panel, default_indicator_specs())
    curves = equity_curves_frame(panel["close"], signals, fee_rate=0.0003)

    assert "benchmark" in curves.columns
    assert "SMA" in curves.columns
    assert curves["benchmark"].iloc[0] == 1.0
    assert curves["SMA"].iloc[0] == 1.0


def test_parabolic_sar_flips_above_price_after_uptrend_break() -> None:
    from investlab.technical_timing.trend import parabolic_sar

    frame = _sample_ohlcv()
    sar = parabolic_sar(frame["high"], frame["low"])

    assert sar.iloc[0] == frame["low"].iloc[0]
    assert (sar.iloc[35:55] < frame["close"].iloc[35:55]).any()
    assert (sar.iloc[-10:] > frame["close"].iloc[-10:]).any()


def test_resolve_timing_assets_supports_paper_index_aliases() -> None:
    from investlab.technical_timing.data_sources import resolve_timing_assets

    assets = resolve_timing_assets("large-cap,399303,chinext")

    assert [asset.key for asset in assets] == ["large-cap", "guozheng2000", "chinext"]


def test_akshare_ohlcv_loader_filters_public_index_daily_data(monkeypatch) -> None:
    from investlab.technical_timing import data_sources

    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    raw = pd.DataFrame(
        {
            "date": dates,
            "open": [1, 2, 3, 4, 5],
            "high": [2, 3, 4, 5, 6],
            "low": [0, 1, 2, 3, 4],
            "close": [1.5, 2.5, 3.5, 4.5, 5.5],
            "volume": [10, 20, 30, 40, 50],
        }
    )
    monkeypatch.setattr(data_sources.ak, "stock_zh_index_daily", lambda symbol: raw)

    asset = data_sources.resolve_timing_assets("large-cap")[0]
    frame = data_sources.load_timing_ohlcv(
        asset, "2020-01-02", "2020-01-04", csv_dir=None, data_source="akshare-ohlcv"
    )

    assert list(frame["close"]) == [2.5, 3.5, 4.5]
    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]
