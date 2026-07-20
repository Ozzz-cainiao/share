from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import pandas as pd  # noqa: PANDAS_OK

TimingDataSource = Literal["akshare-ohlcv", "close-proxy"]


class TechnicalTimingError(ValueError):
    reason: str

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True, slots=True)
class IndicatorSpec:
    name: str
    category: str
    parameters: str
    signal_rule: str
    builder: Callable[[pd.DataFrame], "IndicatorSignal"]


@dataclass(frozen=True, slots=True)
class IndicatorSignal:
    category: str
    buy: pd.Series
    sell: pd.Series


@dataclass(frozen=True, slots=True)
class AssetOhlcv:
    key: str
    name: str
    frame: pd.DataFrame
