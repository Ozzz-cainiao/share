from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def test_report_registry_has_three_default_families() -> None:
    from investlab.publish.report_registry import REPORT_REGISTRY

    assert REPORT_REGISTRY.modes() == ["dca", "difference", "lump"]


def test_report_registry_entries_have_filenames_and_titles() -> None:
    from investlab.publish.report_registry import REPORT_REGISTRY

    entries = {e.mode: e for e in REPORT_REGISTRY.entries()}
    assert entries["lump"].filename == "lump-sum.html"
    assert entries["dca"].filename == "dca.html"
    assert entries["difference"].filename == "difference.html"
    assert entries["lump"].title == "一次投入"
    assert entries["dca"].title == "年度定投"


def test_report_registry_register_and_get_isolated() -> None:
    from investlab.publish.report_registry import ReportDefinition, ReportRegistry

    reg = ReportRegistry()
    reg.register(ReportDefinition("custom", "custom.html", "自定义", "desc"))
    assert reg.get("custom").filename == "custom.html"
    assert reg.modes() == ["custom"]
