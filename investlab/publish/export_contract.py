from __future__ import annotations

from pathlib import Path
from typing import Final, Iterable

EXPORT_PAGE_NAMES: Final[tuple[str, ...]] = ("lump-sum", "dca", "difference")
EXPORT_FORMATS: Final[tuple[str, ...]] = ("jpg", "png")
DEFAULT_WATERMARK: Final[str] = "炼金魔女手记"


def expected_export_filename(asset_key: str, page_name: str, fmt: str = "jpg") -> str:
    if page_name not in EXPORT_PAGE_NAMES:
        raise ValueError(
            f"unknown page name: {page_name}; available: {', '.join(EXPORT_PAGE_NAMES)}"
        )
    if fmt not in EXPORT_FORMATS:
        raise ValueError(f"unknown format: {fmt}; available: {', '.join(EXPORT_FORMATS)}")
    return f"{asset_key}-{page_name}.{fmt}"


def expected_page_html(site_dir: Path, asset_key: str, page_name: str) -> Path:
    return Path(site_dir) / "assets" / asset_key / f"{page_name}.html"


def validate_site_for_export(
    site_dir: Path,
    asset_keys: Iterable[str],
    page_names: Iterable[str] = EXPORT_PAGE_NAMES,
) -> list[Path]:
    site_dir = Path(site_dir)
    pages = tuple(page_names)
    missing: list[Path] = []
    htmls: list[Path] = []
    for asset_key in asset_keys:
        for page_name in pages:
            html = expected_page_html(site_dir, asset_key, page_name)
            if not html.exists():
                missing.append(html)
            else:
                htmls.append(html)
    if missing:
        raise FileNotFoundError(
            f"missing {len(missing)} site page(s) for export: "
            + ", ".join(str(p.relative_to(site_dir)) for p in missing)
        )
    return htmls


def expected_export_paths(
    site_dir: Path,
    asset_keys: Iterable[str],
    output_dir: Path,
    page_names: Iterable[str] = EXPORT_PAGE_NAMES,
    fmt: str = "jpg",
) -> list[Path]:
    validate_site_for_export(site_dir, asset_keys, page_names)
    out = Path(output_dir)
    return [
        out / expected_export_filename(key, page, fmt)
        for key in asset_keys
        for page in page_names
    ]
