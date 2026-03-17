"""Asset allocation calculator with updated parameters.

Updated parameters (2026-03-17):
    cash = 2% (fixed)
    gold = 8% (fixed)
    usBond = 8% (fixed)
    usStock = 20% + 30% * xUsPremium (range 20%-50%)
    cnStock = 20% + remaining * yCnSignal (minimum 20%)
    cnBond = remaining * (1 - yCnSignal)
"""

import numpy as np
from typing import Dict, List, Tuple

# Updated parameters
CASH_RATIO = 0.02
GOLD_RATIO = 0.08
US_BOND_RATIO = 0.08
BASE_US_STOCK = 0.20
US_STOCK_RANGE = 0.30
BASE_CN_STOCK = 0.20

# Asset metadata
ASSET_COLORS = {
    "cash": "#6FAF9F",
    "gold": "#E6D58A",
    "cnBond": "#AEB6D6",
    "cnStock": "#5E93CF",
    "usBond": "#DFA0AC",
    "usStock": "#D77A6C",
}

ASSET_LABELS = {
    "cash": "现金",
    "gold": "黄金",
    "cnBond": "中债",
    "cnStock": "A股",
    "usBond": "美债",
    "usStock": "美股",
}

ASSET_ORDER = ["cash", "gold", "cnBond", "cnStock", "usBond", "usStock"]


def target_weights(x: float, y: float) -> Dict[str, float]:
    """Calculate target weights based on signals and updated parameters.

    Args:
        x: xUsPremium signal (0-1)
        y: yCnSignal signal (0-1)

    Returns:
        Dictionary of asset weights

    Raises:
        ValueError: if weights don't sum to 1
    """
    cash = CASH_RATIO
    gold = GOLD_RATIO
    us_bond = US_BOND_RATIO
    us_stock = BASE_US_STOCK + US_STOCK_RANGE * float(np.clip(x, 0, 1))

    used = cash + gold + us_bond + us_stock + BASE_CN_STOCK
    remaining = max(0.0, 1.0 - used)

    y = float(np.clip(y, 0, 1))
    cn_stock = BASE_CN_STOCK + remaining * y
    cn_bond = remaining * (1.0 - y)

    w = {
        "cash": cash,
        "gold": gold,
        "cnBond": cn_bond,
        "cnStock": cn_stock,
        "usBond": us_bond,
        "usStock": us_stock,
    }

    total = sum(w.values())
    if not np.isclose(total, 1.0, atol=1e-8):
        raise ValueError(f"weights sum to {total}, expected 1")
    return w


def allocation_table(x_vals: List[float], y_vals: List[float]) -> List[Dict]:
    """Generate allocation table for multiple signal values.

    Args:
        x_vals: List of x signal values
        y_vals: List of y signal values

    Returns:
        List of dictionaries with allocation results
    """
    results = []
    for x in x_vals:
        for y in y_vals:
            weights = target_weights(x, y)
            results.append(
                {
                    "x": x,
                    "y": y,
                    **weights,
                    "total_equity": weights["usStock"] + weights["cnStock"],
                    "total_bond": weights["usBond"] + weights["cnBond"],
                    "us_assets": weights["usStock"] + weights["usBond"],
                    "cn_assets": weights["cnStock"] + weights["cnBond"],
                }
            )
    return results


def validate_allocation(weights: Dict[str, float]) -> Tuple[bool, List[str]]:
    """Validate allocation weights.

    Args:
        weights: Dictionary of asset weights

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Check sum
    total = sum(weights.values())
    if not np.isclose(total, 1.0, atol=1e-6):
        errors.append(f"Weights sum to {total:.4f}, expected 1.0")

    # Check individual constraints
    if not np.isclose(weights.get("cash", 0), CASH_RATIO, atol=1e-6):
        errors.append(f"Cash weight {weights.get('cash', 0):.4f} != {CASH_RATIO:.4f}")

    if not np.isclose(weights.get("gold", 0), GOLD_RATIO, atol=1e-6):
        errors.append(f"Gold weight {weights.get('gold', 0):.4f} != {GOLD_RATIO:.4f}")

    if not np.isclose(weights.get("usBond", 0), US_BOND_RATIO, atol=1e-6):
        errors.append(
            f"US Bond weight {weights.get('usBond', 0):.4f} != {US_BOND_RATIO:.4f}"
        )

    us_stock = weights.get("usStock", 0)
    if us_stock < BASE_US_STOCK - 1e-6:
        errors.append(f"US Stock weight {us_stock:.4f} < minimum {BASE_US_STOCK:.4f}")
    if us_stock > BASE_US_STOCK + US_STOCK_RANGE + 1e-6:
        errors.append(
            f"US Stock weight {us_stock:.4f} > maximum {BASE_US_STOCK + US_STOCK_RANGE:.4f}"
        )

    cn_stock = weights.get("cnStock", 0)
    if cn_stock < BASE_CN_STOCK - 1e-6:
        errors.append(f"CN Stock weight {cn_stock:.4f} < minimum {BASE_CN_STOCK:.4f}")

    return len(errors) == 0, errors


def get_asset_summary(weights: Dict[str, float]) -> Dict[str, float]:
    """Calculate summary statistics for allocation.

    Args:
        weights: Dictionary of asset weights

    Returns:
        Dictionary with summary metrics
    """
    return {
        "total_equity": weights.get("usStock", 0) + weights.get("cnStock", 0),
        "total_bond": weights.get("usBond", 0) + weights.get("cnBond", 0),
        "us_assets": weights.get("usStock", 0) + weights.get("usBond", 0),
        "cn_assets": weights.get("cnStock", 0) + weights.get("cnBond", 0),
        "cash_gold": weights.get("cash", 0) + weights.get("gold", 0),
        "equity_bond_ratio": (weights.get("usStock", 0) + weights.get("cnStock", 0))
        / max(weights.get("usBond", 0) + weights.get("cnBond", 0), 1e-6),
    }
