from __future__ import annotations

import argparse
from pathlib import Path

from investlab.scenarios.registry import SCENARIO_REGISTRY, ScenarioEntry
from investlab.technical_timing.scenario_core import run_with_args


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start-date", default="2010-01-04", help="回测开始日期")
    parser.add_argument("--end-date", default="2023-08-31", help="回测结束日期")
    parser.add_argument(
        "--assets",
        default="all",
        help="逗号分隔资产 key/code；默认 all 覆盖论文五个指数",
    )
    parser.add_argument(
        "--data-source",
        choices=("akshare-ohlcv", "close-proxy"),
        default="akshare-ohlcv",
        help="默认用 AkShare 公开 OHLCV；close-proxy 仅用于旧收盘价代理",
    )
    parser.add_argument(
        "--csv-dir", default=None, help="可选 OHLCV CSV 目录，文件名为 <asset-key>.csv"
    )
    parser.add_argument(
        "--fee-rate", type=float, default=0.0003, help="单边交易费率，默认万分之三"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/technical_timing"),
        help="输出目录",
    )


def run(args: argparse.Namespace) -> int:
    return run_with_args(args)


TECHNICAL_TIMING_SCENARIO = ScenarioEntry(
    name="technical-timing",
    description="Replicate default-parameter technical indicator timing tests",
    add_arguments=add_arguments,
    run=run,
)

SCENARIO_REGISTRY.register(TECHNICAL_TIMING_SCENARIO)
