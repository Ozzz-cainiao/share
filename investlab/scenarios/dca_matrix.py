from __future__ import annotations

import pandas as pd


def periodic_irr(cashflows: list[float]) -> float:
    """Return the annual IRR for equally spaced yearly cash flows."""
    if not cashflows or not any(value < 0 for value in cashflows) or not any(
        value > 0 for value in cashflows
    ):
        return float("nan")

    def npv(rate: float) -> float:
        return sum(value / (1.0 + rate) ** period for period, value in enumerate(cashflows))

    low, high = -0.999999, 1.0
    low_value, high_value = npv(low), npv(high)
    while low_value * high_value > 0 and high < 1_000_000:
        high = high * 2.0 + 1.0
        high_value = npv(high)
    if low_value * high_value > 0:
        return float("nan")

    for _ in range(200):
        middle = (low + high) / 2.0
        middle_value = npv(middle)
        if abs(middle_value) < 1e-12:
            return middle
        if low_value * middle_value <= 0:
            high, high_value = middle, middle_value
        else:
            low, low_value = middle, middle_value
    return (low + high) / 2.0


def build_dca_matrices(
    annual: pd.DataFrame, start_year: int, end_year: int
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build annual DCA IRR and terminal-value matrices.

    One unit is invested at each year start. For an N-year period there are N
    equal contributions, followed by liquidation at the end of year N.
    """
    starts = list(range(start_year, end_year + 1))
    periods = list(range(1, end_year - start_year + 2))
    irr = pd.DataFrame(index=periods, columns=starts, dtype=float)
    terminal_values = pd.DataFrame(index=periods, columns=starts, dtype=float)
    available = set(int(year) for year in annual.index)

    for start in starts:
        for years in periods:
            finish = start + years - 1
            contribution_years = list(range(start - 1, finish))
            if finish > end_year or finish not in available:
                continue
            if any(year not in available for year in contribution_years):
                continue
            terminal_price = float(annual.at[finish, "close"])
            shares = sum(1.0 / float(annual.at[year, "close"]) for year in contribution_years)
            terminal_value = shares * terminal_price
            cashflows = [-1.0] * years + [terminal_value]
            irr.at[years, start] = periodic_irr(cashflows) * 100.0
            terminal_values.at[years, start] = terminal_value
    return irr, terminal_values
