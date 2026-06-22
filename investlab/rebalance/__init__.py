"""Corrected multi-asset rebalancing engine and types."""
from investlab.rebalance.engine import run_multi_asset_backtest as run
from investlab.rebalance.models import (
    ExternalFlow,
    MultiAssetBacktestResult,
    MultiAssetContext,
    MultiAssetStrategyProtocol,
    TradeRecord,
)

__all__ = [
    "run",
    "ExternalFlow",
    "MultiAssetBacktestResult",
    "MultiAssetContext",
    "MultiAssetStrategyProtocol",
    "TradeRecord",
]
