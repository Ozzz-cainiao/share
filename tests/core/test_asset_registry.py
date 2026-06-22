from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_current_asset_resolution_behavior_is_characterized() -> None:
    # Given: the legacy publishing and compute asset selectors.
    from asset_catalog import resolve_assets
    from investlab.data import select_assets

    # When: assets are selected through each existing public seam.
    publishing_assets = resolve_assets("large-cap,H00300,nasdaq100,NASDAQXNDX")
    compute_assets = select_assets(["H00300", "NASDAQ100"])

    # Then: current aliases, de-duplication, and source metadata are preserved.
    assert [(asset.key, asset.symbol, asset.source, asset.start_year) for asset in publishing_assets] == [
        ("large-cap", "H00300", "csindex", 2005),
        ("nasdaq100", "NASDAQXNDX", "fred", 2000),
    ]
    assert [(asset.key, asset.symbol, asset.source) for asset in compute_assets] == [
        ("H00300", "H00300", "csindex_tri"),
        ("NASDAQ100", "NASDAQXNDX", "fred"),
    ]


def test_asset_metadata_surfaces_are_backed_by_one_canonical_registry() -> None:
    # Given: the publishing and compute metadata entrypoints.
    import asset_catalog
    from investlab import data
    from investlab.core.asset_registry import REGISTRY

    # When: each surface is materialized from the registry.
    publishing_rows = [
        (asset.key, asset.symbol, asset.source, asset.start_year)
        for asset in asset_catalog.ASSETS
    ]
    compute_rows = [
        (asset.key, asset.symbol, asset.source)
        for asset in data.DEFAULT_ASSETS
    ]
    registry_rows = [
        (
            entry.publish_key,
            entry.publish_symbol,
            entry.publish_source,
            entry.publish_start_year,
        )
        for entry in REGISTRY
    ]
    compute_registry_rows = [
        (entry.compute_key, entry.compute_symbol, entry.compute_source)
        for entry in REGISTRY
        if entry.compute_key is not None
        and entry.compute_symbol is not None
        and entry.compute_source is not None
    ]

    # Then: both public surfaces are derived from the same canonical definitions.
    assert publishing_rows == registry_rows
    assert compute_rows == compute_registry_rows
