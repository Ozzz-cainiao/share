from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import TypeAlias

import pandas as pd

from investlab.rebalance.engine import run_multi_asset_backtest
from investlab.rebalance.experiment import FoldResult
from investlab.rebalance.metrics import compute_twr_metrics
from investlab.rebalance.models import MultiAssetStrategyProtocol
from investlab.rebalance.signals import classify_regime
from investlab.rebalance.statistics import holm_adjust, moving_block_bootstrap, regime_attribution

MetricValue: TypeAlias = float | int | str | bool | None
MetricRow: TypeAlias = dict[str, MetricValue]


def parse_float_csv(raw: str, fallback: list[float]) -> list[float]:
    values = [float(part.strip()) for part in raw.split(",") if part.strip()]
    return values or fallback


def write_research_artifacts(
    output_dir: Path,
    prices_df: pd.DataFrame,
    strategies: list[MultiAssetStrategyProtocol],
    summary_rows: list[MetricRow],
    oos_rows: list[MetricRow],
    folds: list[FoldResult],
    initial_capital: float,
    annual_cash_rate: float,
    fee_rate: float,
    cost_grid: list[float],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_oos(output_dir, oos_rows, folds)
    monthly_returns = _write_per_strategy_artifacts(
        output_dir,
        prices_df,
        strategies,
        initial_capital,
        annual_cash_rate,
        fee_rate,
    )
    signal_rows = _write_signals(output_dir, prices_df)
    _write_regimes(output_dir, monthly_returns, signal_rows)
    _write_bootstrap(output_dir, monthly_returns)
    _write_turnover_costs(output_dir, summary_rows, cost_grid)


def _write_oos(
    output_dir: Path,
    oos_rows: list[MetricRow],
    folds: list[FoldResult],
) -> None:
    pd.DataFrame(oos_rows).to_csv(
        output_dir / "summary_oos.csv",
        index=False,
        encoding="utf-8-sig",
    )
    fold_rows = [
        {
            "fold": fold.fold,
            "train_start": fold.train_start,
            "train_end": fold.train_end,
            "val_start": fold.val_start,
            "val_end": fold.val_end,
            "test_start": fold.test_start,
            "test_end": fold.test_end,
            "selected_id": fold.selected_id,
            "reason": fold.selection_reason,
        }
        for fold in folds
    ]
    pd.DataFrame(fold_rows).to_csv(
        output_dir / "fold_selections.csv",
        index=False,
        encoding="utf-8-sig",
    )


def _write_per_strategy_artifacts(
    output_dir: Path,
    prices_df: pd.DataFrame,
    strategies: list[MultiAssetStrategyProtocol],
    initial_capital: float,
    annual_cash_rate: float,
    fee_rate: float,
) -> pd.DataFrame:
    monthly_returns: dict[str, pd.Series] = {}
    for strategy in strategies:
        result = run_multi_asset_backtest(
            prices_df,
            strategy,
            initial_capital=initial_capital,
            monthly_contribution=0.0,
            annual_cash_rate=annual_cash_rate,
            fee_rate=fee_rate,
        )
        nav = result.nav_curve.rename(strategy.name)
        nav.to_csv(output_dir / f"nav_{strategy.name}.csv", header=True)
        monthly_returns[strategy.name] = nav.resample("ME").last().pct_change().dropna()
        weights_df = pd.DataFrame(result.asset_equity_curves).div(
            result.equity_curve,
            axis=0,
        )
        weights_df.to_csv(output_dir / f"weights_{strategy.name}.csv")
        pd.DataFrame(asdict(trade) for trade in result.trades).to_csv(
            output_dir / f"trades_{strategy.name}.csv",
            index=False,
            encoding="utf-8-sig",
        )
    monthly_df = pd.DataFrame(monthly_returns)
    monthly_df.to_csv(output_dir / "monthly_returns.csv", encoding="utf-8-sig")
    return monthly_df


def _write_signals(output_dir: Path, prices_df: pd.DataFrame) -> list[MetricRow]:
    signal_rows: list[MetricRow] = []
    for date in prices_df.resample("ME").last().index:
        history = prices_df.loc[:date]
        signal = classify_regime(history)
        regime = "structural_bull"
        if not signal.is_structural_bull:
            regime = "other_uptrend" if signal.is_uptrend else "down_or_uncertain"
        signal_rows.append(
            {
                "date": date.strftime("%Y-%m-%d"),
                "regime": regime,
                "is_uptrend": signal.is_uptrend,
                "is_structural_bull": signal.is_structural_bull,
                "dispersion_above_median": signal.dispersion_above_median,
            }
        )
    pd.DataFrame(signal_rows).to_csv(
        output_dir / "signals.csv",
        index=False,
        encoding="utf-8-sig",
    )
    return signal_rows


def _write_regimes(
    output_dir: Path,
    monthly_returns: pd.DataFrame,
    signal_rows: list[MetricRow],
) -> None:
    if monthly_returns.empty or not signal_rows:
        pd.DataFrame().to_csv(output_dir / "regime_summary.csv", index=False)
        return
    regime_series = pd.Series(
        [str(row["regime"]) for row in signal_rows],
        index=pd.to_datetime([str(row["date"]) for row in signal_rows]),
    ).reindex(monthly_returns.index, method="ffill")
    target_column = monthly_returns.columns[0]
    drift = monthly_returns["drift"] if "drift" in monthly_returns else None
    rows = regime_attribution(
        monthly_returns[target_column],
        regime_series,
        drift_returns=drift,
        min_months=1,
    )
    pd.DataFrame(rows).to_csv(
        output_dir / "regime_summary.csv",
        index=False,
        encoding="utf-8-sig",
    )


def _write_bootstrap(output_dir: Path, monthly_returns: pd.DataFrame) -> None:
    if monthly_returns.empty or "drift" not in monthly_returns:
        pd.DataFrame().to_csv(output_dir / "bootstrap_inference.csv", index=False)
        return
    rows: list[MetricRow] = []
    raw_p_values: list[tuple[str, float]] = []
    baseline = monthly_returns["drift"]
    for column in monthly_returns.columns:
        if column == "drift":
            continue
        paired = (monthly_returns[column] - baseline).dropna().to_numpy()
        bootstrap = moving_block_bootstrap(paired)
        raw_p = float(bootstrap["p_value"])
        rows.append({"strategy": column, **bootstrap})
        if pd.notna(raw_p):
            raw_p_values.append((column, raw_p))
    adjusted = {row["strategy"]: row["holm_p"] for row in holm_adjust(raw_p_values)}
    for row in rows:
        row["holm_p"] = adjusted.get(str(row["strategy"]))
    pd.DataFrame(rows).to_csv(
        output_dir / "bootstrap_inference.csv",
        index=False,
        encoding="utf-8-sig",
    )


def _write_turnover_costs(
    output_dir: Path,
    summary_rows: list[MetricRow],
    cost_grid: list[float],
) -> None:
    rows: list[MetricRow] = []
    for summary in summary_rows:
        for cost in cost_grid:
            rows.append(
                {
                    "strategy_name": summary.get("strategy_name"),
                    "one_way_cost": cost,
                    "avg_turnover": summary.get("avg_turnover"),
                    "trade_count": summary.get("trade_count"),
                }
            )
    pd.DataFrame(rows).to_csv(
        output_dir / "turnover_costs.csv",
        index=False,
        encoding="utf-8-sig",
    )
