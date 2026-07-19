from __future__ import annotations

from datetime import date
from pathlib import Path

from investlab.profit_taking.data import (
    H00300_SYMBOL,
    RawH00300Loader,
    load_h00300_prices,
)
from investlab.profit_taking.simple_backtest import (
    SimpleBacktestConfig,
    SimpleBacktestResult,
    run_simple_backtest,
)
from investlab.profit_taking.simple_report import write_simple_outputs


def generate_simple_result(
    output_dir: Path,
    end_date: date,
    raw_loader: RawH00300Loader | None = None,
) -> tuple[SimpleBacktestResult, Path]:
    config = SimpleBacktestConfig()
    prices, provenance = load_h00300_prices(
        H00300_SYMBOL,
        config.start_date,
        end_date,
        loader=raw_loader,
    )
    result = run_simple_backtest(prices, config)
    report_path = write_simple_outputs(
        output_dir,
        result,
        provider=provenance.provider,
        checksum=provenance.checksum_sha256,
    )
    return result, report_path
