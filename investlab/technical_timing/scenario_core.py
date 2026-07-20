from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd  # noqa: PANDAS_OK

from investlab.technical_timing.catalog import default_indicator_specs
from investlab.technical_timing.charts import render_equity_charts
from investlab.technical_timing.data_sources import (
    TimingAsset,
    load_timing_ohlcv,
    resolve_timing_assets,
)
from investlab.technical_timing.engine import (
    equity_curves_frame,
    signal_events_frame,
    summarize_indicator_backtests,
)
from investlab.technical_timing.indicators import build_indicator_signals


def run_with_args(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    assets = resolve_timing_assets(args.assets)
    for asset in assets:
        panel = load_ohlcv_for_asset(
            asset, args.start_date, args.end_date, args.csv_dir, args.data_source
        )
        panel.to_csv(
            output_dir / f"{asset.key}_ohlcv.csv", index=True, index_label="date"
        )
        specs = default_indicator_specs()
        signals = build_indicator_signals(panel, specs)
        summary = summarize_indicator_backtests(panel["close"], signals, args.fee_rate)
        curves = equity_curves_frame(panel["close"], signals, args.fee_rate)
        summary.to_csv(
            output_dir / f"{asset.key}_summary.csv", index=False, encoding="utf-8"
        )
        curves.to_csv(
            output_dir / f"{asset.key}_equity_curves.csv",
            index=True,
            index_label="date",
            encoding="utf-8",
        )
        signal_events_frame(signals).to_csv(
            output_dir / f"{asset.key}_signals.csv",
            index=True,
            index_label="date",
            encoding="utf-8",
        )
        render_equity_charts(curves, specs, asset.key, asset.name, output_dir)
    return 0


def load_ohlcv_for_asset(
    asset: TimingAsset,
    start_date: str,
    end_date: str,
    csv_dir: str | Path | None,
    data_source: str,
) -> pd.DataFrame:
    return load_timing_ohlcv(asset, start_date, end_date, csv_dir, data_source)
