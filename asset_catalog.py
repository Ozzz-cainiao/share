from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssetDefinition:
    key: str
    symbol: str
    name: str
    category: str


ASSETS: tuple[AssetDefinition, ...] = (
    AssetDefinition("all-a", "H00985", "中证全指全收益", "中国A股整体"),
    AssetDefinition("large-cap", "H00300", "沪深300全收益", "中国大盘股"),
    AssetDefinition("csi800", "H00906", "中证800全收益", "中国大中盘股"),
    AssetDefinition("mid-cap", "H00905", "中证500全收益", "中国中小盘股"),
    AssetDefinition("small-cap", "H00852", "中证1000全收益", "中国小盘股"),
)

_BY_KEY = {asset.key: asset for asset in ASSETS}
_BY_SYMBOL = {asset.symbol.upper(): asset for asset in ASSETS}


def asset_help() -> str:
    return "\n".join(
        f"  {asset.key:<10} {asset.symbol:<7} {asset.category}（{asset.name}）"
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
