from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

_MARKER_NAME: Final = ".investlab-calculator-site.json"
_MARKER: Final = {"kind": "investlab.dca-calculator", "schema_version": 1}
_MARKER_TEXT: Final = json.dumps(_MARKER, sort_keys=True, separators=(",", ":")) + "\n"
_PROJECT_ROOT: Final = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class CalculatorBuildError(ValueError):
    reason: str

    def __str__(self) -> str:
        return self.reason


def validate_output_boundary(output_dir: Path) -> None:
    absolute = output_dir.absolute()
    if output_dir.is_symlink() or any(
        ancestor.is_symlink() for ancestor in absolute.parents if ancestor.exists()
    ):
        raise CalculatorBuildError("output path must not contain symbolic links")
    resolved = output_dir.resolve()
    dangerous = {Path("/"), Path.home().resolve(), Path.cwd().resolve(), _PROJECT_ROOT}
    if resolved in dangerous:
        raise CalculatorBuildError("refusing dangerous output directory")
    if output_dir.exists() and not output_dir.is_dir():
        raise CalculatorBuildError("output path must be a directory")
    if output_dir.exists() and not _is_managed(output_dir):
        raise CalculatorBuildError("existing output directory is not a managed site")


def write_site_marker(directory: Path) -> None:
    (directory / _MARKER_NAME).write_text(_MARKER_TEXT, encoding="utf-8")


def publish_managed_site(temporary: Path, output_dir: Path) -> None:
    validate_output_boundary(output_dir)
    if not _is_managed(temporary):
        raise CalculatorBuildError("temporary site is missing its managed marker")
    if not output_dir.exists():
        _replace(temporary, output_dir)
        return
    backup = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}-backup-", dir=output_dir.parent)
    )
    backup.rmdir()
    os.replace(output_dir, backup)
    try:
        _replace(temporary, output_dir)
    except CalculatorBuildError:
        os.replace(backup, output_dir)
        raise
    if not _is_managed(backup):
        raise CalculatorBuildError("managed backup marker was lost; backup preserved")
    shutil.rmtree(backup)


def _replace(source: Path, destination: Path) -> None:
    try:
        os.replace(source, destination)
    except OSError as error:
        raise CalculatorBuildError(
            "could not atomically publish calculator site"
        ) from error


def _is_managed(directory: Path) -> bool:
    marker = directory / _MARKER_NAME
    if marker.is_symlink() or not marker.is_file():
        return False
    try:
        return marker.read_text(encoding="utf-8") == _MARKER_TEXT
    except (OSError, UnicodeDecodeError):
        return False
