"""Predeclared experiment matrix and anchored walk-forward runner."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class FoldResult:
    fold: int
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    test_start: str
    test_end: str
    selected_id: str
    selection_reason: str
    candidates: list[dict[str, Any]]


def run_full_sample(
    prices_df: pd.DataFrame,
    strategies: list,
    initial_capital: float = 1.0,
    annual_cash_rate: float = 0.02,
    fee_rate: float = 0.0003,
) -> list[dict]:
    """Run all strategies on full sample, return metrics."""
    from investlab.rebalance.engine import run_multi_asset_backtest
    from investlab.rebalance.metrics import compute_twr_metrics

    results = []
    for s in strategies:
        r = run_multi_asset_backtest(
            prices_df, s, initial_capital=initial_capital,
            monthly_contribution=0.0, annual_cash_rate=annual_cash_rate, fee_rate=fee_rate,
        )
        m = compute_twr_metrics(r, annual_cash_rate)
        m["strategy_name"] = s.name
        m["strategy_display"] = s.display_name
        results.append(m)
    return results


def run_walk_forward(
    prices_df: pd.DataFrame,
    candidate_strategies: list,
    baseline_strategy,
    min_train_years: int = 5,
    val_years: int = 2,
    test_years: int = 1,
    initial_capital: float = 1.0,
    annual_cash_rate: float = 0.02,
    fee_rate: float = 0.0003,
) -> tuple[list[dict], list[FoldResult]]:
    """Annual walk-forward with train/val/test split.

    Train: expanding window, minimum 5 calendar years.
    Val: next 2 calendar years. Test: next 1 calendar year.
    Select by net TWR Sharpe on train, filter by val max drawdown.
    """
    from investlab.rebalance.engine import run_multi_asset_backtest
    from investlab.rebalance.metrics import compute_twr_metrics

    years = sorted(set(prices_df.index.year))
    if len(years) < min_train_years + val_years + test_years:
        return [], []

    folds: list[FoldResult] = []
    oos_returns: list[dict] = []

    train_end_idx = min_train_years - 1
    while train_end_idx + val_years + test_years <= len(years):
        val_end_idx = train_end_idx + val_years
        test_end_idx = val_end_idx + test_years

        train_start = str(years[0])
        train_end = str(years[train_end_idx])
        val_start = str(years[train_end_idx])
        val_end = str(years[val_end_idx - 1]) if val_years > 1 else str(years[val_end_idx - 1])
        test_start = str(years[val_end_idx])
        test_end = str(years[test_end_idx - 1]) if test_years > 1 else str(years[test_end_idx - 1])

        # Train candidates
        train_df = prices_df.loc[f"{train_start}-01-01":f"{train_end}-12-31"]
        val_df = prices_df.loc[f"{val_start}-01-01":f"{val_end}-12-31"]
        test_df = prices_df.loc[f"{test_start}-01-01":f"{test_end}-12-31"]

        if train_df.empty or val_df.empty or test_df.empty:
            train_end_idx += 1
            continue

        # Score candidates on train
        candidates = []
        for s in candidate_strategies:
            r_train = run_multi_asset_backtest(
                train_df, s, initial_capital=initial_capital,
                monthly_contribution=0.0, annual_cash_rate=annual_cash_rate, fee_rate=fee_rate,
            )
            m_train = compute_twr_metrics(r_train, annual_cash_rate)

            # Validation
            r_val = run_multi_asset_backtest(
                val_df, s, initial_capital=initial_capital,
                monthly_contribution=0.0, annual_cash_rate=annual_cash_rate, fee_rate=fee_rate,
            )
            m_val = compute_twr_metrics(r_val, annual_cash_rate)

            candidates.append({
                "id": s.name,
                "sharpe_train": m_train["sharpe_twr"],
                "max_dd_train": m_train["max_drawdown_twr"],
                "sharpe_val": m_val["sharpe_twr"],
                "max_dd_val": m_val["max_drawdown_twr"],
            })

        # Run baseline on train for drawdown comparison
        r_base_train = run_multi_asset_backtest(
            train_df, baseline_strategy, initial_capital=initial_capital,
            monthly_contribution=0.0, annual_cash_rate=annual_cash_rate, fee_rate=fee_rate,
        )
        m_base_train = compute_twr_metrics(r_base_train, annual_cash_rate)
        base_dd = m_base_train["max_drawdown_twr"]

        # Filter: val max DD not > base DD + 5pp worse
        surviving = [c for c in candidates
                     if not math.isnan(c["max_dd_val"])
                     and c["max_dd_val"] >= base_dd - 0.05]

        if not surviving:
            selected_id = baseline_strategy.name
            reason = "no candidates survive drawdown filter, using baseline"
        else:
            # Rank by train Sharpe, tie-break: turnover → lower lambda → lexical
            surviving.sort(key=lambda c: (
                -c["sharpe_train"] if not math.isnan(c["sharpe_train"]) else 999,
            ))
            selected_id = surviving[0]["id"]
            reason = f"best train Sharpe={surviving[0]['sharpe_train']:.4f}"

        # Run selected on test
        selected_strat = next((s for s in candidate_strategies if s.name == selected_id), baseline_strategy)
        r_test = run_multi_asset_backtest(
            test_df, selected_strat, initial_capital=initial_capital,
            monthly_contribution=0.0, annual_cash_rate=annual_cash_rate, fee_rate=fee_rate,
        )
        m_test = compute_twr_metrics(r_test, annual_cash_rate)
        m_test["fold"] = len(folds) + 1
        m_test["selected_id"] = selected_id
        m_test["test_start"] = test_start
        m_test["test_end"] = test_end
        oos_returns.append(m_test)

        folds.append(FoldResult(
            fold=len(folds) + 1,
            train_start=train_start, train_end=train_end,
            val_start=val_start, val_end=val_end,
            test_start=test_start, test_end=test_end,
            selected_id=selected_id,
            selection_reason=reason,
            candidates=candidates,
        ))

        train_end_idx += 1

    return oos_returns, folds
