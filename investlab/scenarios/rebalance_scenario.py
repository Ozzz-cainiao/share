from __future__ import annotations

from dataclasses import dataclass

from investlab.models import MultiAssetStrategyProtocol


def parse_rebalance_freqs(freq_str: str) -> list[str]:
    """Parse comma-separated frequencies. Defaults to all three."""
    valid = {"monthly", "quarterly", "annual"}
    if not freq_str.strip():
        return ["monthly", "quarterly", "annual"]
    freqs = [f.strip().lower() for f in freq_str.split(",") if f.strip()]
    for f in freqs:
        if f not in valid:
            raise ValueError(f"Invalid frequency: {f!r}. Valid: {sorted(valid)}")
    return freqs


def parse_momentum_lookbacks(lb_str: str) -> list[int]:
    """Parse comma-separated ints. Defaults to [3, 6, 12]."""
    if not lb_str.strip():
        return [3, 6, 12]
    lookbacks: list[int] = []
    for token in lb_str.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            lb = int(token)
        except ValueError:
            raise ValueError(f"Invalid momentum lookback: {token!r}. Must be integer.")
        if lb < 1:
            raise ValueError(f"Momentum lookback must be >= 1, got {lb}")
        lookbacks.append(lb)
    return lookbacks


def parse_thresholds(th_str: str) -> list[float]:
    """Parse comma-separated thresholds. Defaults to [0.05, 0.10]."""
    if not th_str.strip():
        return [0.05, 0.10]
    thresholds: list[float] = []
    for token in th_str.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            t = float(token)
        except ValueError:
            raise ValueError(f"Invalid threshold: {token!r}. Must be float.")
        if t <= 0 or t >= 1:
            raise ValueError(f"Threshold must be in (0, 1), got {t}")
        thresholds.append(t)
    return thresholds


def build_rebalance_strategies(args) -> list[MultiAssetStrategyProtocol]:
    """Build strategy instances from CLI args."""
    from investlab.strategies import (
        EqualWeightCalendarStrategy,
        MomentumFilterRebalanceStrategy,
        MomentumWeightStrategy,
        NoRebalanceStrategy,
        ThresholdRebalanceStrategy,
    )

    freqs = parse_rebalance_freqs(getattr(args, 'rebalance_freqs', ''))
    lookbacks = parse_momentum_lookbacks(getattr(args, 'momentum_lookbacks', ''))
    thresholds = parse_thresholds(getattr(args, 'thresholds', ''))
    momentum_modes = getattr(args, 'momentum_modes', 'filter,weight')
    modes = [m.strip().lower() for m in momentum_modes.split(",") if m.strip()]
    top_n_values = [int(x.strip()) for x in getattr(args, 'momentum_top_n', '2').split(",") if x.strip()]

    strategies: list[MultiAssetStrategyProtocol] = []

    # Baseline
    strategies.append(NoRebalanceStrategy())

    # Calendar rebalance
    for freq in freqs:
        strategies.append(EqualWeightCalendarStrategy(frequency=freq))

    # Threshold rebalance
    for th in thresholds:
        strategies.append(ThresholdRebalanceStrategy(threshold=th))

    # Momentum filter
    if "filter" in modes:
        for freq in freqs:
            for lb in lookbacks:
                strategies.append(MomentumFilterRebalanceStrategy(frequency=freq, momentum_lookback=lb))

    # Momentum weight
    if "weight" in modes:
        for lb in lookbacks:
            for tn in top_n_values:
                strategies.append(MomentumWeightStrategy(momentum_lookback=lb, top_n=tn))

    return strategies


# ---- Scenario entry point ----

def add_arguments(parser) -> None:
    parser.add_argument("--start", default="2015-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default="2025-12-31", help="End date YYYY-MM-DD")
    parser.add_argument(
        "--assets",
        default="H00300,H00905,H00852",
        help="Comma-separated asset keys",
    )
    parser.add_argument(
        "--rebalance-freqs",
        default="monthly,quarterly,annual",
        help="Comma-separated: monthly,quarterly,annual",
    )
    parser.add_argument(
        "--thresholds",
        default="0.05,0.10",
        help="Comma-separated deviation thresholds (e.g. 0.05,0.10)",
    )
    parser.add_argument(
        "--momentum-lookbacks",
        default="3,6,12",
        help="Comma-separated lookback months",
    )
    parser.add_argument(
        "--momentum-modes",
        default="filter,weight",
        help="Comma-separated: filter,weight",
    )
    parser.add_argument(
        "--momentum-top-n",
        default="2",
        help="Comma-separated top-N values for MomentumWeightStrategy",
    )
    parser.add_argument("--monthly", type=float, default=1.0, help="Monthly contribution")
    parser.add_argument("--cash-rate", type=float, default=0.02, help="Annual cash yield")
    parser.add_argument("--fee-rate", type=float, default=0.0003, help="Single-side fee rate")
    parser.add_argument("--initial-capital", type=float, default=1.0, help="Lump-sum initial capital (0 for contribution-only)")
    parser.add_argument("--panel", default="index", choices=["index", "etf", "both"], help="Research panel")
    parser.add_argument("--output-dir", default="output/rebalance", help="Output directory")


def run(args) -> int:
    """Enhanced run using corrected engine with structured artifacts."""
    import json, math
    from pathlib import Path

    import numpy as np
    import pandas as pd

    from investlab.data import select_assets
    from investlab.rebalance.data import build_index_panel, write_manifest
    from investlab.rebalance.engine import run_multi_asset_backtest
    from investlab.rebalance.experiment import run_full_sample, run_walk_forward
    from investlab.rebalance.metrics import compute_twr_metrics
    from investlab.rebalance.statistics import (
        moving_block_bootstrap,
        holm_adjust,
        parameter_surface,
    )
    from investlab.rebalance.strategies import (
        CalendarEqualWeight,
        DriftStrategy,
        FixedBlendStrategy,
        InverseVolatility,
        RegimeAdaptiveStrategy,
        ThresholdEqualWeight,
    )
    from investlab.utils import xirr

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build index panel with provenance
    df, meta = build_index_panel(args.start, args.end)
    write_manifest(meta, output_dir)

    # Build primary study strategies
    strategies = [
        DriftStrategy(),
        CalendarEqualWeight(frequency="monthly"),
        CalendarEqualWeight(frequency="quarterly"),
        CalendarEqualWeight(frequency="annual"),
        ThresholdEqualWeight(threshold=0.05),
        ThresholdEqualWeight(threshold=0.10),
        InverseVolatility(),
        FixedBlendStrategy(lam=0.50, band=0.05),
        RegimeAdaptiveStrategy(),
    ]

    # Run full sample
    results = run_full_sample(
        df, strategies,
        initial_capital=getattr(args, 'initial_capital', 1.0),
        annual_cash_rate=args.cash_rate,
        fee_rate=args.fee_rate,
    )

    # Walk-forward
    candidates = [DriftStrategy()] + [
        CalendarEqualWeight(frequency=f) for f in ["monthly", "quarterly"]
    ] + [
        FixedBlendStrategy(lam=l, band=b)
        for l in [0.25, 0.50, 0.75]
        for b in [0.05]
    ]
    oos_results, folds = run_walk_forward(
        df, candidates, DriftStrategy(),
        initial_capital=getattr(args, 'initial_capital', 1.0),
        annual_cash_rate=args.cash_rate,
        fee_rate=args.fee_rate,
    )

    # Parameter surface
    surface_df = parameter_surface(results)

    # Bootstrap: compare best strategy vs drift
    best = max(results, key=lambda r: r.get("sharpe_twr", -999))
    drift = next(r for r in results if r.get("strategy_name") == "drift")

    # Simplified bootstrap (if monthly returns available)
    bootstrap_result = {"note": "bootstrap requires monthly return series from engine"}

    # Output CSVs
    summary_df = pd.DataFrame(results)
    summary_df.to_csv(output_dir / "summary_full_sample.csv", index=False, encoding="utf-8-sig")

    if oos_results:
        pd.DataFrame(oos_results).to_csv(output_dir / "summary_oos.csv", index=False, encoding="utf-8-sig")

    if folds:
        fold_rows = []
        for f in folds:
            fold_rows.append({
                "fold": f.fold, "train_start": f.train_start, "train_end": f.train_end,
                "val_start": f.val_start, "val_end": f.val_end,
                "test_start": f.test_start, "test_end": f.test_end,
                "selected_id": f.selected_id, "reason": f.selection_reason,
            })
        pd.DataFrame(fold_rows).to_csv(output_dir / "fold_selections.csv", index=False, encoding="utf-8-sig")

    if len(surface_df) > 0:
        surface_df.to_csv(output_dir / "parameter_surface.csv", index=False, encoding="utf-8-sig")

    # Strategy catalog
    catalog = []
    for s in strategies:
        catalog.append({
            "id": s.name, "display_name": s.display_name,
            "family": getattr(s, "family", ""),
        })
    with open(output_dir / "strategy_catalog.json", "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    print(f"Rebalance research complete. {len(results)} strategies, {len(folds)} walk-forward folds.")
    print(f"  Full sample: {output_dir / 'summary_full_sample.csv'}")
    if oos_results:
        print(f"  OOS:         {output_dir / 'summary_oos.csv'}")
    print(f"  Manifest:    {output_dir / 'run_manifest.json'}")

    # T14-compatible HTML (placeholder until T11)
    build_html_report([{
        "strategy_name": r.get("strategy_name", ""),
        "strategy_display_name": r.get("strategy_display", r.get("strategy_name", "")),
        "xirr": r.get("xirr_investor", r.get("ann_return_twr", 0)),
        "xirr_excess": r.get("ann_return_twr", 0) - drift.get("ann_return_twr", 0) if drift else 0,
        "sharpe": r.get("sharpe_twr", 0),
        "max_drawdown": r.get("max_drawdown_twr", 0),
        "trade_count": r.get("trade_count", 0),
        "final_value": r.get("final_value", 0),
        "total_contribution": r.get("total_contribution", 1),
    } for r in results], str(output_dir / "rebalance_comparison.html"))

    return 0


from investlab.scenarios.registry import SCENARIO_REGISTRY, ScenarioEntry

REBALANCE_SCENARIO = ScenarioEntry(
    name="rebalance",
    description="Multi-asset rebalancing backtest (equal-weight, momentum filter, momentum weight)",
    add_arguments=add_arguments,
    run=run,
)
SCENARIO_REGISTRY.register(REBALANCE_SCENARIO)
