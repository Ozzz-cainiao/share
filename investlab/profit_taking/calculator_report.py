from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final, TypedDict

import pandas as pd  # noqa: PANDAS_OK

from investlab.profit_taking.calculator_data import (
    CalculatorDataError,
    build_calculator_payload,
)
from investlab.profit_taking.calculator_publish import (
    CalculatorBuildError,
    publish_managed_site,
    validate_output_boundary,
    write_site_marker,
)
from investlab.profit_taking.data import H00300_PROVIDER, H00300_SYMBOL

_START: Final = date(2006, 1, 1)
_ACTUAL_START: Final = date(2006, 1, 4)
_END: Final = date(2026, 7, 17)
_RETRIEVED_AT: Final = datetime(2026, 7, 17, tzinfo=UTC)
_STATIC_DIR: Final = Path(__file__).with_name("calculator_static")
_SOURCE_DIR: Final = Path(__file__).with_name("calculator_source")
_SOURCE_PAYLOAD: Final = _SOURCE_DIR / "h00300-tri-source.json"
_SOURCE_MANIFEST: Final = _SOURCE_DIR / "h00300-tri-manifest.json"
_PROVIDED_CSV_PROVIDER: Final = "provided_csv"
_ASSETS: Final = (
    "calculator.css",
    "calculator-core.js",
    "calculator-integrity.js",
    "calculator-app.js",
    "calculator-chart.js",
)


@dataclass(frozen=True, slots=True)
class CalculatorSite:
    index_path: Path
    checksum_sha256: str
    start_date: date
    end_date: date


class _BuiltProvenance(TypedDict):
    actual_coverage: list[str]
    checksum_sha256: str


class _BuiltPayload(TypedDict):
    prices: list[list[str | float]]
    provenance: _BuiltProvenance


class _SourceManifest(TypedDict):
    normalized_checksum_sha256: str
    normalized_coverage: list[str]
    normalized_row_count: int
    source_payload_sha256: str
    source_row_count: int


def build_calculator_site(
    output_dir: Path,
    *,
    prices_csv: Path | None = None,
) -> CalculatorSite:
    validate_output_boundary(output_dir)
    source = _parse_source(prices_csv)
    try:
        if source is None:
            payload_text = build_calculator_payload(
                H00300_SYMBOL,
                _START,
                _END,
                loader=_bundled_source_loader,
                provider=H00300_PROVIDER,
                retrieved_at_utc=_RETRIEVED_AT,
            )
        else:
            payload_text = build_calculator_payload(
                H00300_SYMBOL,
                _START,
                _END,
                cached_price_csv=source,
                provider=_PROVIDED_CSV_PROVIDER,
                retrieved_at_utc=_RETRIEVED_AT,
            )
    except CalculatorDataError as error:
        raise CalculatorBuildError(str(error)) from error
    payload: _BuiltPayload = json.loads(payload_text)
    coverage = payload["provenance"]["actual_coverage"]
    if coverage != [_ACTUAL_START.isoformat(), _END.isoformat()]:
        raise CalculatorBuildError(
            f"price coverage must be {_ACTUAL_START.isoformat()} through {_END.isoformat()}"
        )
    checksum = str(payload["provenance"]["checksum_sha256"])
    if source is None:
        _verify_bundled_result(payload)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent)
    )
    try:
        _write_site(temporary, payload_text, checksum)
        publish_managed_site(temporary, output_dir)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return CalculatorSite(output_dir / "index.html", checksum, _ACTUAL_START, _END)


def _bundled_source_loader(
    _symbol: str,
    _start: date,
    _end: date,
) -> pd.DataFrame:
    try:
        source_bytes = _SOURCE_PAYLOAD.read_bytes()
        manifest = json.loads(_SOURCE_MANIFEST.read_text(encoding="utf-8"))
        source = json.loads(source_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CalculatorDataError("bundled H00300 source could not be read") from error
    if not isinstance(manifest, dict) or not isinstance(source, dict):
        raise CalculatorDataError("bundled H00300 source must contain JSON objects")
    source_checksum = hashlib.sha256(source_bytes).hexdigest()
    if source_checksum != manifest.get("source_payload_sha256"):
        raise CalculatorDataError("bundled H00300 source checksum mismatch")
    prices = source.get("prices")
    if not isinstance(prices, list) or len(prices) != manifest.get("source_row_count"):
        raise CalculatorDataError("bundled H00300 source row count mismatch")
    try:
        return pd.DataFrame(prices, columns=["日期", "收盘"])
    except (AssertionError, TypeError, ValueError) as error:
        raise CalculatorDataError("bundled H00300 source rows are malformed") from error


def _verify_bundled_result(payload: _BuiltPayload) -> None:
    try:
        manifest: _SourceManifest = json.loads(
            _SOURCE_MANIFEST.read_text(encoding="utf-8")
        )
        prices = payload["prices"]
        provenance = payload["provenance"]
        matches = (
            len(prices) == manifest["normalized_row_count"]
            and provenance["actual_coverage"] == manifest["normalized_coverage"]
            and provenance["checksum_sha256"] == manifest["normalized_checksum_sha256"]
        )
    except (
        KeyError,
        OSError,
        TypeError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise CalculatorBuildError(
            "bundled H00300 manifest could not be verified"
        ) from error
    if not matches:
        raise CalculatorBuildError("bundled H00300 normalized result mismatch")


def _parse_source(prices_csv: Path | None) -> Path | None:
    if prices_csv is None:
        return None
    if prices_csv.is_symlink():
        raise CalculatorBuildError("prices CSV must not be a symbolic link")
    if not prices_csv.is_file():
        raise CalculatorBuildError("prices CSV must be an existing regular file")
    return prices_csv


def _write_site(directory: Path, payload_text: str, checksum: str) -> None:
    versions: dict[str, str] = {}
    for name in _ASSETS:
        content = (_STATIC_DIR / name).read_bytes()
        (directory / name).write_bytes(content)
        versions[name] = hashlib.sha256(content).hexdigest()[:12]
    html = (_STATIC_DIR / "index.template.html").read_text(encoding="utf-8")
    for name, version in versions.items():
        html = html.replace(f"./{name}", f"./{name}?v={version}")
    html = html.replace("__CALCULATOR_DATA_SHA256__", checksum)
    payload_checksum = hashlib.sha256(payload_text.encode("utf-8")).hexdigest()
    html = html.replace("__CALCULATOR_PAYLOAD_SHA256__", payload_checksum)
    disclosure = (
        "<div><dt>计算假设</dt><dd>使用全收益指数，不考虑手续费、税费和滑点</dd></div>"
    )
    html = html.replace("</dl>\n      </footer>", f"{disclosure}</dl>\n      </footer>")
    (directory / "index.html").write_text(html, encoding="utf-8")
    assets = directory / "assets"
    assets.mkdir()
    (assets / "h00300-prices.json").write_text(payload_text, encoding="utf-8")
    write_site_marker(directory)
