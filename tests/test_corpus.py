"""Corpus-loader smoke tests."""

from __future__ import annotations

from zarnitsa.corpus import load_snapshot
from zarnitsa.types import SourceTier


def test_sample_entry_loads() -> None:
    entries = load_snapshot("2026-05")
    assert entries, "snapshot 2026-05 should contain at least the sample entry"
    sample = next((e for e in entries if "2014-doctrine" in e.id), None)
    assert sample is not None, "sample doctrine entry not found"
    assert sample.tier == SourceTier.PRIMARY_DOCTRINE
    assert "НАТО" in sample.keywords
