from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ReportDefinition:
    mode: str
    filename: str
    title: str
    description: str


class ReportRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, ReportDefinition] = {}

    def register(self, entry: ReportDefinition) -> None:
        if entry.mode in self._entries:
            raise ValueError(f"report already registered: {entry.mode}")
        self._entries[entry.mode] = entry

    def modes(self) -> list[str]:
        return sorted(self._entries)

    def entries(self) -> list[ReportDefinition]:
        return [self._entries[m] for m in self.modes()]

    def get(self, mode: str) -> ReportDefinition:
        if mode not in self._entries:
            raise KeyError(mode)
        return self._entries[mode]


REPORT_REGISTRY: Final[ReportRegistry] = ReportRegistry()
for _report in (
    ReportDefinition("lump", "lump-sum.html", "一次投入", "一次投入后的滚动 CAGR"),
    ReportDefinition("dca", "dca.html", "年度定投", "每年年初等额投入的滚动 IRR"),
    ReportDefinition(
        "difference", "difference.html", "定投与一次投入之差", "定投 IRR 减一次投入 CAGR"
    ),
):
    REPORT_REGISTRY.register(_report)
