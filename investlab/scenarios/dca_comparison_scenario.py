from __future__ import annotations

import argparse
from pathlib import Path

from investlab.scenarios.registry import SCENARIO_REGISTRY, ScenarioEntry
from investlab.scenarios.dca_comparison_core import run_with_args as run_dca_comparison


def add_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start-year", type=int, default=None, help="覆盖标的默认起始年份")
    parser.add_argument("--end-year", type=int, default=2025, help="终止年份，默认 2025")
    parser.add_argument("--assets", default="all-a", help="逗号分隔的标的 key 或代码；all 表示全部")
    parser.add_argument("--symbol", default=None, help="自定义中证指数代码（覆盖 --assets）")
    parser.add_argument("--name", default=None, help="自定义指数显示名称")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output/dca_comparison"), help="输出目录"
    )
    parser.add_argument(
        "--no-known-adjustments",
        action="store_true",
        help="关闭已知的数据质量修正，使用数据源原始点位",
    )


def run(args: argparse.Namespace) -> int:
    return run_dca_comparison(args)


DCA_COMPARISON_SCENARIO = ScenarioEntry(
    name="dca-comparison",
    description="Compare lump-sum CAGR with annual DCA IRR matrices (CSV + HTML)",
    add_arguments=add_arguments,
    run=run,
)

SCENARIO_REGISTRY.register(DCA_COMPARISON_SCENARIO)
