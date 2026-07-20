from __future__ import annotations

import pandas as pd  # noqa: PANDAS_OK

from investlab.technical_timing.models import (
    IndicatorSignal,
    IndicatorSpec,
    TechnicalTimingError,
)


def build_indicator_signals(
    frame: pd.DataFrame, specs: tuple[IndicatorSpec, ...]
) -> dict[str, IndicatorSignal]:
    normalized = _normalize_ohlcv(frame)
    return {spec.name: spec.builder(normalized) for spec in specs}


def _normalize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    required = ("open", "high", "low", "close", "volume")
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise TechnicalTimingError(f"missing OHLCV column(s): {', '.join(missing)}")
    normalized = frame.loc[:, required].copy()
    for column in required:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    return normalized.dropna(subset=["close"]).ffill()
