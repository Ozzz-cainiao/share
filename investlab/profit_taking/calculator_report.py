from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Final

from investlab.profit_taking.calculator_data import (
    CalculatorDataError,
    build_calculator_payload,
)
from investlab.profit_taking.data import H00300_SYMBOL

_START: Final = date(2006, 1, 1)
_END: Final = date(2026, 7, 17)
_RETRIEVED_AT: Final = datetime(2026, 7, 17, tzinfo=UTC)
_STATIC_DIR: Final = Path(__file__).with_name("calculator_static")
_ASSETS: Final = (
    "calculator.css",
    "calculator-core.js",
    "calculator-app.js",
    "calculator-chart.js",
)


@dataclass(frozen=True, slots=True)
class CalculatorBuildError(ValueError):
    reason: str

    def __str__(self) -> str:
        return self.reason


@dataclass(frozen=True, slots=True)
class CalculatorSite:
    index_path: Path
    checksum_sha256: str
    start_date: date
    end_date: date


def build_calculator_site(
    output_dir: Path,
    *,
    prices_csv: Path | None = None,
) -> CalculatorSite:
    source = _parse_source(prices_csv)
    try:
        payload_text = build_calculator_payload(
            H00300_SYMBOL,
            _START,
            _END,
            cached_price_csv=source,
            retrieved_at_utc=_RETRIEVED_AT,
        )
    except CalculatorDataError as error:
        raise CalculatorBuildError(str(error)) from error
    payload = json.loads(payload_text)
    coverage = payload["provenance"]["actual_coverage"]
    if coverage != [_START.isoformat(), _END.isoformat()]:
        raise CalculatorBuildError(
            f"price coverage must be {_START.isoformat()} through {_END.isoformat()}"
        )
    checksum = str(payload["provenance"]["checksum_sha256"])
    _require_output_boundary(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent)
    )
    try:
        _write_site(temporary, payload_text)
        _replace_site(temporary, output_dir)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return CalculatorSite(output_dir / "index.html", checksum, _START, _END)


def _parse_source(prices_csv: Path | None) -> Path | None:
    if prices_csv is None:
        return None
    if prices_csv.is_symlink():
        raise CalculatorBuildError("prices CSV must not be a symbolic link")
    if not prices_csv.is_file():
        raise CalculatorBuildError("prices CSV must be an existing regular file")
    return prices_csv


def _require_output_boundary(output_dir: Path) -> None:
    if output_dir.is_symlink():
        raise CalculatorBuildError("output directory must not be a symbolic link")
    if output_dir.exists() and not output_dir.is_dir():
        raise CalculatorBuildError("output path must be a directory")


def _write_site(directory: Path, payload_text: str) -> None:
    versions: dict[str, str] = {}
    for name in _ASSETS:
        content = (_STATIC_DIR / name).read_bytes()
        (directory / name).write_bytes(content)
        versions[name] = hashlib.sha256(content).hexdigest()[:12]
    html = (_STATIC_DIR / "index.template.html").read_text(encoding="utf-8")
    for name, version in versions.items():
        html = html.replace(f"./{name}", f"./{name}?v={version}")
    disclosure = (
        "<div><dt>计算假设</dt><dd>使用全收益指数，不考虑手续费、税费和滑点</dd></div>"
    )
    html = html.replace("</dl>\n      </footer>", f"{disclosure}</dl>\n      </footer>")
    (directory / "index.html").write_text(html, encoding="utf-8")
    assets = directory / "assets"
    assets.mkdir()
    (assets / "h00300-prices.json").write_text(payload_text, encoding="utf-8")


def _replace_site(temporary: Path, output_dir: Path) -> None:
    backup = output_dir.with_name(f".{output_dir.name}-previous")
    if backup.exists():
        shutil.rmtree(backup)
    if output_dir.exists():
        os.replace(output_dir, backup)
    try:
        os.replace(temporary, output_dir)
    except OSError as error:
        if backup.exists():
            os.replace(backup, output_dir)
        raise CalculatorBuildError(
            "could not atomically publish calculator site"
        ) from error
    if backup.exists():
        shutil.rmtree(backup)
