"""Regime, stability, cost and multiple-testing-aware inference."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def regime_attribution(
    monthly_returns: pd.DataFrame,
    regime_series: pd.Series,
    drift_returns: pd.Series | None = None,
    min_months: int = 24,
) -> list[dict]:
    """Attribute next-month returns to prior regime. Returns per-regime stats."""
    results = []
    for regime_name in regime_series.unique():
        mask = regime_series == regime_name
        n = mask.sum()
        if n < min_months:
            continue

        rets = monthly_returns.loc[mask]
        ann_ret = float(rets.mean() * 12) if len(rets) > 0 else math.nan
        ann_vol = float(rets.std() * math.sqrt(12)) if len(rets) > 1 else math.nan
        cum_ret = float((1.0 + rets).prod() - 1.0)

        excess = None
        if drift_returns is not None:
            drift_rets = drift_returns.loc[mask]
            excess_mean = float((rets - drift_rets).mean())
            excess_ann = excess_mean * 12 if not math.isnan(excess_mean) else math.nan
            excess = excess_ann

        results.append({
            "regime": regime_name,
            "n_months": int(n),
            "ann_return": ann_ret,
            "ann_volatility": ann_vol,
            "cumulative_return": cum_ret,
            "excess_vs_drift_ann": excess,
        })
    return results


def parameter_surface(
    summaries: list[dict],
) -> pd.DataFrame:
    """Build lambda x band parameter surface from strategy results."""
    rows = []
    for s in summaries:
        name = s.get("strategy_name", "")
        if name.startswith("blend_"):
            parts = name.replace("blend_", "").split("_")
            try:
                lam = float(parts[0])
                bp = int(parts[1].replace("bp", ""))
                rows.append({
                    "lambda": lam,
                    "band_bp": bp,
                    "sharpe": s.get("sharpe_twr", math.nan),
                    "ann_return": s.get("ann_return_twr", math.nan),
                    "max_drawdown": s.get("max_drawdown_twr", math.nan),
                    "avg_turnover": s.get("avg_turnover", 0.0),
                })
            except (ValueError, IndexError):
                pass
    return pd.DataFrame(rows)


def moving_block_bootstrap(
    paired_excess: np.ndarray,
    block_size: int = 6,
    n_replicates: int = 10000,
    seed: int = 20260622,
) -> dict:
    """Moving-block bootstrap on paired monthly excess returns.

    Returns 95% CI, mean, and two-sided p-value.
    """
    rng = np.random.default_rng(seed)
    n = len(paired_excess)
    if n < block_size * 2:
        return {"mean": float(np.mean(paired_excess)), "ci_lower": np.nan, "ci_upper": np.nan,
                "p_value": np.nan, "n": n, "block_size": block_size}

    n_blocks = n // block_size
    means = np.empty(n_replicates)

    for i in range(n_replicates):
        block_indices = rng.integers(0, n - block_size + 1, size=n_blocks)
        sample = np.concatenate([paired_excess[idx:idx + block_size] for idx in block_indices])
        means[i] = np.mean(sample[:n])  # truncate to original length

    ci_lower = float(np.percentile(means, 2.5))
    ci_upper = float(np.percentile(means, 97.5))
    mean_est = float(np.mean(means))

    # Two-sided p-value: fraction of bootstrap means more extreme than 0
    p_value = float(min(
        np.mean(means <= 0),
        np.mean(means >= 0),
    ) * 2.0)

    return {
        "mean": mean_est,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "p_value": p_value,
        "n": n,
        "block_size": block_size,
        "n_replicates": n_replicates,
    }


def holm_adjust(p_values: list[tuple[str, float]]) -> list[dict]:
    """Holm-Bonferroni adjustment for multiple comparisons."""
    sorted_pv = sorted(p_values, key=lambda x: x[1])
    m = len(sorted_pv)
    adjusted = []
    for k, (name, p) in enumerate(sorted_pv):
        adj = min(p * (m - k), 1.0)
        if k > 0:
            adj = max(adj, adjusted[-1]["holm_p"])  # monotonicity
        adjusted.append({"strategy": name, "raw_p": p, "holm_p": adj, "rank": k + 1})
    return adjusted
