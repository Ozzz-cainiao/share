"""Asset allocation module for signal-driven portfolio construction."""

from investlab.allocation.calculator import (
    CASH_RATIO,
    GOLD_RATIO,
    US_BOND_RATIO,
    BASE_US_STOCK,
    US_STOCK_RANGE,
    BASE_CN_STOCK,
    ASSET_COLORS,
    ASSET_LABELS,
    ASSET_ORDER,
    target_weights,
    allocation_table,
    validate_allocation,
    get_asset_summary,
)

from investlab.allocation.signals import (
    build_cn_signal_series,
    build_us_signal_series,
    get_signals,
)

__all__ = [
    # Calculator
    "CASH_RATIO",
    "GOLD_RATIO",
    "US_BOND_RATIO",
    "BASE_US_STOCK",
    "US_STOCK_RANGE",
    "BASE_CN_STOCK",
    "ASSET_COLORS",
    "ASSET_LABELS",
    "ASSET_ORDER",
    "target_weights",
    "allocation_table",
    "validate_allocation",
    "get_asset_summary",
    # Signals
    "build_cn_signal_series",
    "build_us_signal_series",
    "get_signals",
]
