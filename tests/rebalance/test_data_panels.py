"""Index and ETF panel tests."""
import pandas as pd
from investlab.rebalance.data import build_index_panel, build_etf_panel, PanelMetadata
from unittest.mock import patch, MagicMock

def test_build_index_panel_metadata():
    """Index panel must return DataFrame and valid metadata."""
    df, meta = build_index_panel("2020-01-01", "2023-12-31")
    assert isinstance(df, pd.DataFrame)
    assert isinstance(meta, PanelMetadata)
    assert meta.panel_type == "index"
    assert len(meta.symbols) == 3
    assert "H00300" in meta.symbols
    assert len(meta.price_sha256) == 16
    assert meta.common_dates > 0

def test_manifest_writable(tmp_path):
    from investlab.rebalance.data import write_manifest
    meta = PanelMetadata("test", ["X"], ["X"], "test", "2020", "2023",
                         "2020", "2023", 100, 0, 100, "abc123", "now")
    write_manifest(meta, tmp_path)
    assert (tmp_path / "run_manifest.json").exists()
