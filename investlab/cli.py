from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from investlab.data import fetch_price_series, select_assets
from investlab.engine import run_backtest
from investlab.metrics import summarize_result
from investlab.strategies import DcaStrategy, DrawdownTimingStrategy, parse_drawdown_rules


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reusable backtest runner for DCA and timing strategies."
    )
    parser.add_argument("--start", default="2005-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default="2026-03-09", help="End date YYYY-MM-DD")
    parser.add_argument(
        "--assets",
        default="",
        help="Comma-separated asset keys, e.g. H00300,H00906,H00905,SPY,QQQ",
    )
    parser.add_argument(
        "--drawdown-rules",
        default="10:6,20:12",
        help="Comma-separated rules: drawdown_percent:max_wait_months",
    )
    parser.add_argument("--monthly", type=float, default=1.0, help="Monthly contribution")
    parser.add_argument("--cash-rate", type=float, default=0.02, help="Annual cash yield")
    parser.add_argument("--fee-rate", type=float, default=0.0003, help="Single-side fee rate")
    parser.add_argument("--output-dir", default="output/framework", help="Output directory")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "price_series"
    data_dir.mkdir(parents=True, exist_ok=True)

    asset_keys = [x.strip() for x in args.assets.split(",")] if args.assets.strip() else None
    assets = select_assets(asset_keys)
    rules = parse_drawdown_rules(args.drawdown_rules)

    summaries: list[dict] = []
    for asset in assets:
        prices = fetch_price_series(asset, args.start, args.end)
        prices.to_frame("close").to_csv(
            data_dir / f"{asset.key}_close.csv",
            encoding="utf-8-sig",
        )

        baseline_result = run_backtest(
            prices=prices,
            strategy=DcaStrategy(),
            monthly_contribution=args.monthly,
            annual_cash_rate=args.cash_rate,
            fee_rate=args.fee_rate,
        )
        baseline_summary = summarize_result(asset, baseline_result, risk_free_rate=args.cash_rate)
        baseline_summary.xirr_excess = 0.0
        summaries.append(baseline_summary.__dict__)

        for drawdown, max_wait in rules:
            strategy = DrawdownTimingStrategy(
                drawdown_threshold=drawdown,
                max_wait_months=max_wait,
            )
            result = run_backtest(
                prices=prices,
                strategy=strategy,
                monthly_contribution=args.monthly,
                annual_cash_rate=args.cash_rate,
                fee_rate=args.fee_rate,
            )
            summary = summarize_result(asset, result, risk_free_rate=args.cash_rate)
            summary.xirr_excess = summary.xirr - baseline_summary.xirr
            summaries.append(summary.__dict__)

    summary_df = pd.DataFrame(summaries)
    summary_df = summary_df.sort_values(
        ["asset_key", "strategy_name"],
        ignore_index=True,
    )
    summary_long_path = output_dir / "summary_long.csv"
    summary_df.to_csv(summary_long_path, index=False, encoding="utf-8-sig")

    xirr_pivot = summary_df.pivot_table(
        index=["asset_key", "asset_name"],
        columns="strategy_display_name",
        values="xirr",
    ).reset_index()
    xirr_pivot_path = output_dir / "summary_xirr_wide.csv"
    xirr_pivot.to_csv(xirr_pivot_path, index=False, encoding="utf-8-sig")

    excess_pivot = summary_df.pivot_table(
        index=["asset_key", "asset_name"],
        columns="strategy_display_name",
        values="xirr_excess",
    ).reset_index()
    excess_pivot_path = output_dir / "summary_xirr_excess_wide.csv"
    excess_pivot.to_csv(excess_pivot_path, index=False, encoding="utf-8-sig")

    print("Framework backtest complete.")
    print(f"Summary(long):  {summary_long_path}")
    print(f"Summary(xirr):  {xirr_pivot_path}")
    print(f"Summary(excess):{excess_pivot_path}")


if __name__ == "__main__":
    main()
