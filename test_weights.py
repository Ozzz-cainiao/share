#!/usr/bin/env python3
"""Test the updated allocation weights calculation."""

import numpy as np

# Updated parameters
CASH_RATIO = 0.02
GOLD_RATIO = 0.08
US_BOND_RATIO = 0.08
BASE_US_STOCK = 0.20
US_STOCK_RANGE = 0.30
BASE_CN_STOCK = 0.20


def target_weights(x: float, y: float):
    """Calculate target weights based on signals and updated parameters."""
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


# Test cases
test_cases = [
    (0.0, 0.0, "Minimum signals"),
    (1.0, 1.0, "Maximum signals"),
    (0.5, 0.5, "Middle signals"),
    (0.0, 1.0, "Min US, Max CN"),
    (1.0, 0.0, "Max US, Min CN"),
    (0.3, 0.7, "Example 1"),
    (0.8, 0.2, "Example 2"),
]

print("Testing updated allocation parameters:")
print(f"Cash: {CASH_RATIO:.0%}, Gold: {GOLD_RATIO:.0%}, US Bond: {US_BOND_RATIO:.0%}")
print(f"US Stock: {BASE_US_STOCK:.0%}-{BASE_US_STOCK + US_STOCK_RANGE:.0%}")
print(f"CN Stock minimum: {BASE_CN_STOCK:.0%}")
print()

for x, y, desc in test_cases:
    weights = target_weights(x, y)
    total = sum(weights.values())
    print(f"{desc}: x={x:.1f}, y={y:.1f}")
    for asset, weight in weights.items():
        print(f"  {asset:8s}: {weight:6.2%}")
    print(f"  Total: {total:6.2%}")

    # Verify constraints
    assert np.isclose(total, 1.0, atol=1e-8), f"Total not 1: {total}"
    assert weights["usStock"] >= BASE_US_STOCK - 1e-8, (
        f"US stock below min: {weights['usStock']}"
    )
    assert weights["usStock"] <= BASE_US_STOCK + US_STOCK_RANGE + 1e-8, (
        f"US stock above max: {weights['usStock']}"
    )
    assert weights["cnStock"] >= BASE_CN_STOCK - 1e-8, (
        f"CN stock below min: {weights['cnStock']}"
    )
    print()

# Test edge cases
print("Edge case: high cash+gold would exceed 1?")
# With our parameters, cash+gold = 10%, US bond = 8%, US stock min = 20%, CN stock min = 20%
# Total minimum = 10% + 8% + 20% + 20% = 58%, so remaining = 42%
# This should work fine
weights = target_weights(0.0, 0.0)
print(f"Minimum allocation leaves {weights['cnBond']:.2%} for CN bond")
print()

print("All tests passed!")
