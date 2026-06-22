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
