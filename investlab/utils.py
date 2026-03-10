from __future__ import annotations

import math

import pandas as pd


def month_diff(a: pd.Timestamp, b: pd.Timestamp) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month)


def xnpv(rate: float, cashflows: list[tuple[pd.Timestamp, float]]) -> float:
    t0 = cashflows[0][0]
    return sum(
        amount / (1.0 + rate) ** ((dt - t0).days / 365.25)
        for dt, amount in cashflows
    )


def xirr(cashflows: list[tuple[pd.Timestamp, float]]) -> float:
    values = [v for _, v in cashflows]
    if not any(v < 0 for v in values) or not any(v > 0 for v in values):
        return math.nan

    low, high = -0.9999, 10.0
    npv_low, npv_high = xnpv(low, cashflows), xnpv(high, cashflows)
    if npv_low * npv_high > 0:
        return math.nan

    for _ in range(200):
        mid = (low + high) / 2.0
        npv_mid = xnpv(mid, cashflows)
        if abs(npv_mid) < 1e-10:
            return mid
        if npv_low * npv_mid < 0:
            high, npv_high = mid, npv_mid
        else:
            low, npv_low = mid, npv_mid
    return (low + high) / 2.0
