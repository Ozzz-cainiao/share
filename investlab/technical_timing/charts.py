from __future__ import annotations

from pathlib import Path

import pandas as pd  # noqa: PANDAS_OK

from investlab.technical_timing.models import IndicatorSpec


def render_equity_charts(
    curves: pd.DataFrame,
    specs: tuple[IndicatorSpec, ...],
    asset_key: str,
    asset_name: str,
    output_dir: Path,
) -> None:
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = [
        "PingFang SC",
        "Arial Unicode MS",
        "Heiti TC",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False
    output_dir.mkdir(parents=True, exist_ok=True)
    category_map = _category_indicators(specs)
    _render_chart(
        curves,
        ["benchmark", *[spec.name for spec in specs]],
        f"{asset_name} - 32 technical timing strategies",
        output_dir / f"{asset_key}_equity_all.png",
        plt,
    )
    for category, indicators in category_map.items():
        _render_chart(
            curves,
            ["benchmark", *indicators],
            f"{asset_name} - {category} indicators",
            output_dir / f"{asset_key}_equity_{category}.png",
            plt,
        )


def _category_indicators(specs: tuple[IndicatorSpec, ...]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for spec in specs:
        result.setdefault(spec.category, []).append(spec.name)
    return result


def _render_chart(
    curves: pd.DataFrame,
    columns: list[str],
    title: str,
    path: Path,
    plt,
) -> None:
    selected = [column for column in columns if column in curves.columns]
    figure, axis = plt.subplots(figsize=(13, 7), dpi=160)
    for column in selected:
        width = 2.4 if column == "benchmark" else 1.2
        alpha = 1.0 if column == "benchmark" else 0.78
        axis.plot(
            curves.index, curves[column], label=column, linewidth=width, alpha=alpha
        )
    axis.set_title(title)
    axis.set_xlabel("Date")
    axis.set_ylabel("Net value")
    axis.grid(True, alpha=0.25)
    axis.legend(loc="upper left", ncols=3, fontsize=8)
    figure.tight_layout()
    figure.savefig(path)
    plt.close(figure)
