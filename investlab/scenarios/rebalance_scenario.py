from __future__ import annotations

from pathlib import Path

import pandas as pd

from investlab.models import MultiAssetStrategyProtocol
from investlab.rebalance.artifacts import parse_float_csv, write_research_artifacts
from investlab.rebalance.data import build_index_panel, write_manifest
from investlab.rebalance.experiment import run_full_sample, run_walk_forward
from investlab.rebalance.report import generate_research_report
from investlab.rebalance.statistics import parameter_surface
from investlab.rebalance.strategies import (
    CalendarEqualWeight,
    DriftStrategy,
    FixedBlendStrategy,
    FixedRatioRebalanceStrategy,
    FixedRatioStrategy,
    InverseVolatility,
    RegimeAdaptiveStrategy,
    ThresholdEqualWeight,
)
from investlab.scenarios.registry import SCENARIO_REGISTRY, ScenarioEntry


def parse_rebalance_freqs(freq_str: str) -> list[str]:
    valid = {"monthly", "quarterly", "annual"}
    if not freq_str.strip():
        return ["monthly", "quarterly", "annual"]
    freqs = [freq.strip().lower() for freq in freq_str.split(",") if freq.strip()]
    for freq in freqs:
        if freq not in valid:
            raise ValueError(f"Invalid frequency: {freq!r}. Valid: {sorted(valid)}")
    return freqs


def parse_momentum_lookbacks(lb_str: str) -> list[int]:
    if not lb_str.strip():
        return [3, 6, 12]
    lookbacks: list[int] = []
    for token in lb_str.split(","):
        stripped = token.strip()
        if not stripped:
            continue
        try:
            lookback = int(stripped)
        except ValueError as exc:
            raise ValueError(
                f"Invalid momentum lookback: {stripped!r}. Must be integer."
            ) from exc
        if lookback < 1:
            raise ValueError(f"Momentum lookback must be >= 1, got {lookback}")
        lookbacks.append(lookback)
    return lookbacks


def parse_thresholds(th_str: str) -> list[float]:
    if not th_str.strip():
        return [0.05, 0.10]
    thresholds: list[float] = []
    for token in th_str.split(","):
        stripped = token.strip()
        if not stripped:
            continue
        try:
            threshold = float(stripped)
        except ValueError as exc:
            raise ValueError(
                f"Invalid threshold: {stripped!r}. Must be float."
            ) from exc
        if threshold <= 0 or threshold >= 1:
            raise ValueError(f"Threshold must be in (0, 1), got {threshold}")
        thresholds.append(threshold)
    return thresholds


def build_rebalance_strategies(args) -> list[MultiAssetStrategyProtocol]:
    from investlab.strategies import (
        EqualWeightCalendarStrategy,
        MomentumFilterRebalanceStrategy,
        MomentumWeightStrategy,
        NoRebalanceStrategy,
        ThresholdRebalanceStrategy,
    )

    freqs = parse_rebalance_freqs(getattr(args, "rebalance_freqs", ""))
    lookbacks = parse_momentum_lookbacks(getattr(args, "momentum_lookbacks", ""))
    thresholds = parse_thresholds(getattr(args, "thresholds", ""))
    modes = [
        mode.strip().lower()
        for mode in getattr(args, "momentum_modes", "filter,weight").split(",")
        if mode.strip()
    ]
    top_n_values = [
        int(value.strip())
        for value in getattr(args, "momentum_top_n", "2").split(",")
        if value.strip()
    ]

    strategies: list[MultiAssetStrategyProtocol] = [NoRebalanceStrategy()]
    strategies.extend(EqualWeightCalendarStrategy(frequency=freq) for freq in freqs)
    strategies.extend(ThresholdRebalanceStrategy(threshold=threshold) for threshold in thresholds)
    if "filter" in modes:
        for freq in freqs:
            for lookback in lookbacks:
                strategies.append(
                    MomentumFilterRebalanceStrategy(
                        frequency=freq,
                        momentum_lookback=lookback,
                    )
                )
    if "weight" in modes:
        for lookback in lookbacks:
            for top_n in top_n_values:
                strategies.append(
                    MomentumWeightStrategy(
                        momentum_lookback=lookback,
                        top_n=top_n,
                    )
                )
    return strategies


def add_arguments(parser) -> None:
    parser.add_argument("--start", default="2015-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default="2025-12-31", help="End date YYYY-MM-DD")
    parser.add_argument("--assets", default="H00300,H00905,H00852")
    parser.add_argument("--rebalance-freqs", default="monthly,quarterly,annual")
    parser.add_argument("--thresholds", default="0.05,0.10")
    parser.add_argument("--momentum-lookbacks", default="3,6,12")
    parser.add_argument("--momentum-modes", default="filter,weight")
    parser.add_argument("--momentum-top-n", default="2")
    parser.add_argument("--monthly", type=float, default=1.0)
    parser.add_argument("--cash-rate", type=float, default=0.02)
    parser.add_argument("--fee-rate", type=float, default=0.0003)
    parser.add_argument("--initial-capital", type=float, default=1.0)
    parser.add_argument("--panel", default="index", choices=["index", "etf", "both"])
    parser.add_argument("--cost-grid", default="0.0005,0.0010,0.0020")
    parser.add_argument("--fixed-lambdas", default="0,0.25,0.50,0.75,1")
    parser.add_argument("--fixed-bands", default="0,0.05,0.10")
    parser.add_argument("--walk-forward", action="store_true", default=True)
    parser.add_argument("--no-walk-forward", action="store_false", dest="walk_forward")
    parser.add_argument("--contribution-sensitivity", action="store_true")
    parser.add_argument("--output-dir", default="output/rebalance")


def _research_strategies(
    lambdas: list[float],
    bands: list[float],
) -> list[MultiAssetStrategyProtocol]:
    return [
        DriftStrategy(),
        CalendarEqualWeight(frequency="monthly"),
        CalendarEqualWeight(frequency="quarterly"),
        CalendarEqualWeight(frequency="annual"),
        ThresholdEqualWeight(threshold=0.05),
        ThresholdEqualWeight(threshold=0.10),
        InverseVolatility(),
        *[FixedBlendStrategy(lam=lam, band=band) for lam in lambdas for band in bands],
        RegimeAdaptiveStrategy(),
        FixedRatioStrategy(target={"H00300": 0.50, "H00905": 0.30, "H00852": 0.20}),
        FixedRatioRebalanceStrategy(
            target={"H00300": 0.50, "H00905": 0.30, "H00852": 0.20}
        ),
        FixedRatioStrategy(target={"H00300": 0.20, "H00905": 0.30, "H00852": 0.50}),
        FixedRatioRebalanceStrategy(
            target={"H00300": 0.20, "H00905": 0.30, "H00852": 0.50}
        ),
        FixedRatioStrategy(target={"H00300": 0.40, "H00905": 0.20, "H00852": 0.40}),
        FixedRatioRebalanceStrategy(
            target={"H00300": 0.40, "H00905": 0.20, "H00852": 0.40}
        ),
    ]


def _walk_forward_candidates() -> list[MultiAssetStrategyProtocol]:
    return [
        DriftStrategy(),
        CalendarEqualWeight(frequency="monthly"),
        CalendarEqualWeight(frequency="quarterly"),
        *[FixedBlendStrategy(lam=lam, band=0.05) for lam in [0.25, 0.50, 0.75]],
    ]


def _write_primary_outputs(
    output_dir: Path,
    results: list[dict],
    strategies: list[MultiAssetStrategyProtocol],
) -> None:
    pd.DataFrame(results).to_csv(
        output_dir / "summary_full_sample.csv",
        index=False,
        encoding="utf-8-sig",
    )
    pd.DataFrame(
        {
            "id": strategy.name,
            "display_name": strategy.display_name,
            "family": getattr(strategy, "family", ""),
        }
        for strategy in strategies
    ).to_json(
        output_dir / "strategy_catalog.json",
        orient="records",
        force_ascii=False,
        indent=2,
    )


def run(args) -> int:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prices_df, meta = build_index_panel(args.start, args.end)
    write_manifest(meta, output_dir)

    lambdas = parse_float_csv(args.fixed_lambdas, [0.0, 0.25, 0.50, 0.75, 1.0])
    bands = parse_float_csv(args.fixed_bands, [0.0, 0.05, 0.10])
    cost_grid = parse_float_csv(args.cost_grid, [0.0005, 0.0010, 0.0020])
    strategies = _research_strategies(lambdas, bands)
    initial_capital = getattr(args, "initial_capital", 1.0)

    results = run_full_sample(
        prices_df,
        strategies,
        initial_capital=initial_capital,
        annual_cash_rate=args.cash_rate,
        fee_rate=args.fee_rate,
    )
    oos_results, folds = ([], [])
    if args.walk_forward:
        oos_results, folds = run_walk_forward(
            prices_df,
            _walk_forward_candidates(),
            DriftStrategy(),
            initial_capital=initial_capital,
            annual_cash_rate=args.cash_rate,
            fee_rate=args.fee_rate,
        )

    _write_primary_outputs(output_dir, results, strategies)
    parameter_surface(results).to_csv(
        output_dir / "parameter_surface.csv",
        index=False,
        encoding="utf-8-sig",
    )
    write_research_artifacts(
        output_dir=output_dir,
        prices_df=prices_df,
        strategies=strategies,
        summary_rows=results,
        oos_rows=oos_results,
        folds=folds,
        initial_capital=initial_capital,
        annual_cash_rate=args.cash_rate,
        fee_rate=args.fee_rate,
        cost_grid=cost_grid,
    )
    drift_twr = next(
        (row["ann_return_twr"] for row in results if row.get("strategy_name") == "drift"),
        0,
    )
    generate_research_report(results, output_dir, drift_twr)

    print(f"Rebalance research complete. {len(results)} strategies, {len(folds)} walk-forward folds.")
    print(f"  Full sample: {output_dir / 'summary_full_sample.csv'}")
    if oos_results:
        print(f"  OOS:         {output_dir / 'summary_oos.csv'}")
    print(f"  HTML report: {output_dir / 'rebalance_comparison.html'}")
    return 0


REBALANCE_SCENARIO = ScenarioEntry(
    name="rebalance",
    description="Multi-asset rebalancing backtest (equal-weight, momentum filter, momentum weight)",
    add_arguments=add_arguments,
    run=run,
)
SCENARIO_REGISTRY.register(REBALANCE_SCENARIO)
