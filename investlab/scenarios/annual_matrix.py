from __future__ import annotations

import pandas as pd


def year_end_closes(closes: pd.Series) -> pd.DataFrame:
    frame = closes.rename("close").to_frame()
    grouped = frame.groupby(frame.index.year, sort=True)
    return pd.DataFrame(
        {
            "date": grouped.apply(lambda series: series.index[-1], include_groups=False),
            "close": grouped["close"].last(),
        }
    )


def apply_known_adjustments(
    annual: pd.DataFrame, symbol: str
) -> tuple[pd.DataFrame, list[str]]:
    adjusted = annual.copy()
    notes: list[str] = []
    if symbol.upper() == "H00300" and 2005 in adjusted.index:
        adjusted.loc[adjusted.index >= 2005, "close"] *= 1.026
        notes.append(
            "H00300 已应用2005年分红估算修正：2005年及以后财富指数乘以1.026，"
            "2005年收益由-7.65%修正为约-5.25%"
        )
    return adjusted, notes


def build_matrix(
    annual: pd.DataFrame, start_year: int, end_year: int
) -> tuple[pd.DataFrame, list[str]]:
    starts = list(range(start_year, end_year + 1))
    holding_periods = list(range(1, end_year - start_year + 2))
    matrix = pd.DataFrame(index=holding_periods, columns=starts, dtype=float)
    warnings: list[str] = []

    available = {int(year) for year in annual.index}
    required = set(range(start_year - 1, end_year + 1))
    missing = sorted(required - available)
    if missing:
        warnings.append("缺少年末数据：" + "、".join(map(str, missing)))

    for start in starts:
        base_year = start - 1
        if base_year not in available:
            continue
        base = float(annual.at[base_year, "close"])
        for years in holding_periods:
            finish = start + years - 1
            if finish > end_year or finish not in available:
                continue
            terminal = float(annual.at[finish, "close"])
            if base > 0 and terminal > 0:
                matrix.at[years, start] = (
                    (terminal / base) ** (1.0 / years) - 1.0
                ) * 100.0

    if matrix.notna().sum().sum() == 0:
        raise RuntimeError("无法计算任何收益率，请检查年份范围和指数历史数据")
    return matrix, warnings
