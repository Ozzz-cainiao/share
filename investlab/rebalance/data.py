"""Research panels with provenance manifests."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from investlab.core.asset_registry import REGISTRY
from investlab.data import fetch_price_series, select_assets


@dataclass
class PanelMetadata:
    panel_type: str  # "index" | "etf"
    symbols: list[str]
    names: list[str]
    source_endpoint: str
    requested_start: str
    requested_end: str
    actual_start: str
    actual_end: str
    n_observations: int
    n_missing: int
    common_dates: int
    price_sha256: str
    download_timestamp: str
    backfilled_history: bool = False
    unavailable_reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        result = {}
        for k, v in self.__dict__.items():
            if v is not None:
                if hasattr(v, 'item'):
                    result[k] = v.item()
                elif isinstance(v, dict):
                    result[k] = {kk: vv.item() if hasattr(vv, 'item') else vv for kk, vv in v.items()}
                else:
                    result[k] = v
        return result


def build_index_panel(start: str, end: str) -> tuple[pd.DataFrame, PanelMetadata]:
    """Primary research panel: H00300, H00905, H00852 total-return."""
    assets = select_assets(["H00300", "H00905", "H00852"])
    series_dict = {}
    for asset in assets:
        prices = fetch_price_series(asset, start, end)
        series_dict[asset.key] = prices

    df = pd.DataFrame(series_dict)
    common = df.dropna().index

    # SHA-256 of normalized prices
    sha = hashlib.sha256(
        df.loc[common].to_csv(index=False).encode()
    ).hexdigest()[:16]

    meta = PanelMetadata(
        panel_type="index",
        symbols=[a.symbol for a in assets],
        names=[a.name for a in assets],
        source_endpoint="csindex_tri (akshare)",
        requested_start=start,
        requested_end=end,
        actual_start=str(common[0].date()) if len(common) > 0 else "",
        actual_end=str(common[-1].date()) if len(common) > 0 else "",
        n_observations=sum(len(series_dict[k]) for k in series_dict),
        n_missing=df.isna().sum().sum(),
        common_dates=len(common),
        price_sha256=sha,
        download_timestamp=datetime.now(timezone.utc).isoformat(),
        backfilled_history=False,
    )
    return df.loc[common].ffill(), meta


def build_etf_panel(start: str, end: str) -> tuple[pd.DataFrame | None, PanelMetadata | None]:
    """Investability validation panel: 510300, 510500, 512100."""
    try:
        etf_symbols = ["510300", "510500", "512100"]
        series_dict = {}
        for sym in etf_symbols:
            spec = type("Spec", (), {
                "key": sym, "name": sym, "source": "us_etf_qfq", "symbol": sym,
                "total_return": True,
            })()
            prices = fetch_price_series(spec, start, end)
            series_dict[sym] = prices

        df = pd.DataFrame(series_dict)
        common = df.dropna().index
        if len(common) < 252:
            meta = PanelMetadata(
                panel_type="etf", symbols=etf_symbols, names=etf_symbols,
                source_endpoint="us_etf_qfq (akshare)", requested_start=start,
                requested_end=end, actual_start="", actual_end="",
                n_observations=0, n_missing=0, common_dates=0,
                price_sha256="", download_timestamp="",
                unavailable_reason=f"Only {len(common)} common trading days, need >=252"
            )
            return None, meta

        sha = hashlib.sha256(
            df.loc[common].to_csv(index=False).encode()
        ).hexdigest()[:16]

        meta = PanelMetadata(
            panel_type="etf", symbols=etf_symbols, names=etf_symbols,
            source_endpoint="us_etf_qfq (akshare)", requested_start=start,
            requested_end=end, actual_start=str(common[0].date()),
            actual_end=str(common[-1].date()),
            n_observations=sum(len(series_dict[k]) for k in series_dict),
            n_missing=df.isna().sum().sum(), common_dates=len(common),
            price_sha256=sha, download_timestamp=datetime.now(timezone.utc).isoformat(),
        )
        return df.loc[common].ffill(), meta
    except Exception as e:
        meta = PanelMetadata(
            panel_type="etf", symbols=["510300", "510500", "512100"],
            names=["510300", "510500", "512100"],
            source_endpoint="us_etf_qfq (akshare)", requested_start=start,
            requested_end=end, actual_start="", actual_end="",
            n_observations=0, n_missing=0, common_dates=0,
            price_sha256="", download_timestamp="",
            unavailable_reason=str(e)
        )
        return None, meta


def write_manifest(meta: PanelMetadata, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "run_manifest.json").write_text(
        json.dumps(meta.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
