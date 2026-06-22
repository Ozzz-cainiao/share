from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from investlab.core.asset_registry import REGISTRY


@dataclass(frozen=True)
class AssetDefinition:
    key: str
    symbol: str
    name: str
    category: str
    source: str = "csindex"
    start_year: int = 2005


ASSETS: Final[tuple[AssetDefinition, ...]] = tuple(
    AssetDefinition(
        key=entry.publish_key,
        symbol=entry.publish_symbol,
        name=entry.publish_name,
        category=entry.publish_category,
        source=entry.publish_source,
        start_year=entry.publish_start_year,
    )
    for entry in REGISTRY
)

_BY_KEY: Final[dict[str, AssetDefinition]] = {asset.key: asset for asset in ASSETS}
_BY_SYMBOL: Final[dict[str, AssetDefinition]] = {
    asset.symbol.upper(): asset for asset in ASSETS
}


def asset_help() -> str:
    return "\n".join(
        f"  {asset.key:<10} {asset.symbol:<7} {asset.start_year}–  {asset.category}（{asset.name}）"
        for asset in ASSETS
    )


def resolve_assets(value: str) -> list[AssetDefinition]:
    tokens = [token.strip() for token in value.split(",") if token.strip()]
    if not tokens:
        raise ValueError("至少选择一个投资标的")
    if any(token.lower() == "all" for token in tokens):
        return list(ASSETS)

    selected: list[AssetDefinition] = []
    unknown: list[str] = []
    for token in tokens:
        asset = _BY_KEY.get(token.lower()) or _BY_SYMBOL.get(token.upper())
        if asset is None:
            unknown.append(token)
        elif asset not in selected:
            selected.append(asset)
    if unknown:
        raise ValueError(
            f"未知标的：{', '.join(unknown)}。可用 key/code："
            + ", ".join(f"{a.key}/{a.symbol}" for a in ASSETS)
        )
    return selected
