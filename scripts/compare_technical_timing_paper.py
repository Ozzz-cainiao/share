from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd  # noqa: PANDAS_OK


PAPER_HS300_ROWS: tuple[dict[str, float | str], ...] = (
    {
        "indicator": "SMA",
        "sharpe": 0.26,
        "annual_return": 0.0272,
        "annual_excess": 0.0233,
        "annual_volatility": 0.1453,
        "holding_win_rate": 0.3558,
        "payoff_ratio": 2.49,
        "max_drawdown": 0.3028,
        "annual_turnover": 15.78,
    },
    {
        "indicator": "EMA",
        "sharpe": 0.35,
        "annual_return": 0.0404,
        "annual_excess": 0.0365,
        "annual_volatility": 0.1431,
        "holding_win_rate": 0.3239,
        "payoff_ratio": 3.52,
        "max_drawdown": 0.2704,
        "annual_turnover": 10.78,
    },
    {
        "indicator": "KAMA",
        "sharpe": 0.39,
        "annual_return": 0.0439,
        "annual_excess": 0.0399,
        "annual_volatility": 0.1302,
        "holding_win_rate": 0.4426,
        "payoff_ratio": 2.03,
        "max_drawdown": 0.2926,
        "annual_turnover": 9.26,
    },
    {
        "indicator": "MACD",
        "sharpe": 0.28,
        "annual_return": 0.0297,
        "annual_excess": 0.0257,
        "annual_volatility": 0.1440,
        "holding_win_rate": 0.3577,
        "payoff_ratio": 2.31,
        "max_drawdown": 0.3415,
        "annual_turnover": 18.67,
    },
    {
        "indicator": "AROON",
        "sharpe": 0.50,
        "annual_return": 0.0634,
        "annual_excess": 0.0594,
        "annual_volatility": 0.1440,
        "holding_win_rate": 0.4590,
        "payoff_ratio": 2.32,
        "max_drawdown": 0.3115,
        "annual_turnover": 9.26,
    },
    {
        "indicator": "ADX",
        "sharpe": 0.54,
        "annual_return": 0.0630,
        "annual_excess": 0.0591,
        "annual_volatility": 0.1284,
        "holding_win_rate": 0.3712,
        "payoff_ratio": 3.14,
        "max_drawdown": 0.1944,
        "annual_turnover": 20.03,
    },
    {
        "indicator": "DPO",
        "sharpe": 0.38,
        "annual_return": 0.0447,
        "annual_excess": 0.0407,
        "annual_volatility": 0.1408,
        "holding_win_rate": 0.2963,
        "payoff_ratio": 3.76,
        "max_drawdown": 0.2662,
        "annual_turnover": 16.39,
    },
    {
        "indicator": "SAR",
        "sharpe": 0.16,
        "annual_return": 0.0131,
        "annual_excess": 0.0092,
        "annual_volatility": 0.1409,
        "holding_win_rate": 0.4026,
        "payoff_ratio": 1.76,
        "max_drawdown": 0.3530,
        "annual_turnover": 23.37,
    },
    {
        "indicator": "AD",
        "sharpe": 0.27,
        "annual_return": 0.0286,
        "annual_excess": 0.0246,
        "annual_volatility": 0.1469,
        "holding_win_rate": 0.4219,
        "payoff_ratio": 4.95,
        "max_drawdown": 0.3243,
        "annual_turnover": 9.41,
    },
    {
        "indicator": "OBV",
        "sharpe": 0.33,
        "annual_return": 0.0403,
        "annual_excess": 0.0363,
        "annual_volatility": 0.1470,
        "holding_win_rate": 0.4671,
        "payoff_ratio": 1.91,
        "max_drawdown": 0.3802,
        "annual_turnover": 14.57,
    },
    {
        "indicator": "MFI",
        "sharpe": 0.09,
        "annual_return": 0.0042,
        "annual_excess": 0.0002,
        "annual_volatility": 0.1161,
        "holding_win_rate": 0.6667,
        "payoff_ratio": 0.73,
        "max_drawdown": 0.3895,
        "annual_turnover": 1.37,
    },
    {
        "indicator": "EOM",
        "sharpe": 0.46,
        "annual_return": 0.0752,
        "annual_excess": 0.0713,
        "annual_volatility": 0.1998,
        "holding_win_rate": 0.4274,
        "payoff_ratio": 3.09,
        "max_drawdown": 0.2587,
        "annual_turnover": 35.51,
    },
    {
        "indicator": "MAAMT",
        "sharpe": 0.88,
        "annual_return": 0.1124,
        "annual_excess": 0.1084,
        "annual_volatility": 0.1316,
        "holding_win_rate": 0.5239,
        "payoff_ratio": 2.71,
        "max_drawdown": 0.2683,
        "annual_turnover": 53.88,
    },
    {
        "indicator": "FI",
        "sharpe": 0.25,
        "annual_return": 0.0259,
        "annual_excess": 0.0220,
        "annual_volatility": 0.1413,
        "holding_win_rate": 0.6219,
        "payoff_ratio": 1.22,
        "max_drawdown": 0.2192,
        "annual_turnover": 34.45,
    },
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if not args.summary.exists():
        raise SystemExit(
            f"summary file not found: {args.summary}\n"
            "Run technical-timing first, or point --summary to the directory you used. "
            "Example: --summary output/technical_timing_acceptance/large-cap_summary.csv"
        )
    actual = pd.read_csv(args.summary)
    paper = pd.DataFrame(PAPER_HS300_ROWS)
    merged = paper.merge(actual, on="indicator", suffixes=("_paper", "_actual"))
    metrics = [
        "sharpe",
        "annual_return",
        "annual_excess",
        "annual_volatility",
        "holding_win_rate",
        "payoff_ratio",
        "max_drawdown",
        "annual_turnover",
    ]
    for metric in metrics:
        merged[f"{metric}_diff"] = (
            merged[f"{metric}_actual"] - merged[f"{metric}_paper"]
        )
    ordered = ["indicator"]
    for metric in metrics:
        ordered.extend([f"{metric}_paper", f"{metric}_actual", f"{metric}_diff"])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    merged.loc[:, ordered].to_csv(args.output, index=False)
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
