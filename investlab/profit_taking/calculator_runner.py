from __future__ import annotations

import argparse
from pathlib import Path
from typing import Final, Sequence

from investlab.profit_taking.calculator_report import build_calculator_site

_DEFAULT_OUTPUT: Final = Path("output/dca_strategy_calculator")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="构建沪深300全收益指数定投策略比较计算器"
    )
    parser.add_argument("--output-dir", type=Path, default=_DEFAULT_OUTPUT)
    parser.add_argument(
        "--prices-csv",
        type=Path,
        help="可选的缓存价格 CSV；省略时从默认数据提供方构建",
    )
    args = parser.parse_args(argv)
    site = build_calculator_site(args.output_dir, prices_csv=args.prices_csv)
    print(
        f"built {site.index_path} "
        f"coverage={site.start_date.isoformat()}..{site.end_date.isoformat()} "
        f"sha256={site.checksum_sha256}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
