from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class AssetRegistryEntry:
    publish_key: str
    publish_symbol: str
    publish_name: str
    publish_category: str
    publish_source: str = "csindex"
    publish_start_year: int = 2005
    compute_key: str | None = None
    compute_name: str | None = None
    compute_source: str | None = None
    compute_symbol: str | None = None
    compute_total_return: bool = True


REGISTRY: Final[tuple[AssetRegistryEntry, ...]] = (
    AssetRegistryEntry("all-a", "H00985", "中证全指全收益", "中国A股整体"),
    AssetRegistryEntry(
        "large-cap",
        "H00300",
        "沪深300全收益",
        "中国大盘股",
        compute_key="H00300",
        compute_name="沪深300全收益",
        compute_source="csindex_tri",
        compute_symbol="H00300",
    ),
    AssetRegistryEntry(
        "csi800",
        "H00906",
        "中证800全收益",
        "中国大中盘股",
        compute_key="H00906",
        compute_name="中证800全收益",
        compute_source="csindex_tri",
        compute_symbol="H00906",
    ),
    AssetRegistryEntry(
        "mid-cap",
        "H00905",
        "中证500全收益",
        "中国中小盘股",
        compute_key="H00905",
        compute_name="中证500全收益",
        compute_source="csindex_tri",
        compute_symbol="H00905",
    ),
    AssetRegistryEntry(
    "small-cap",
    "H00852",
    "中证1000全收益",
    "中国小盘股",
    compute_key="H00852",
    compute_name="中证1000全收益",
    compute_source="csindex_tri",
    compute_symbol="H00852",
),
    AssetRegistryEntry(
        "sp500",
        "SPY",
        "标普500（SPY含息）",
        "美国大盘股",
        "us_etf_total_return",
        1993,
        "SPY",
        "标普500（SPY前复权）",
        "us_etf_qfq",
        "SPY",
    ),
    AssetRegistryEntry(
        "nasdaq100",
        "NASDAQXNDX",
        "纳斯达克100（XNDX全收益）",
        "美国科技大盘股",
        "fred",
        2000,
        "NASDAQ100",
        "纳指100（XNDX全收益）",
        "fred",
        "NASDAQXNDX",
    ),
)
