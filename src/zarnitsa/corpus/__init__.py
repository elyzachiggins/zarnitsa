"""Knowledge corpus — doctrine, speeches, lessons-learned, with provenance tags."""

from zarnitsa.corpus.entry import (
    CorpusEntry,
    EntryError,
    SnapshotReport,
    load_snapshot,
    load_snapshot_report,
)
from zarnitsa.corpus.retrieval import Retriever

__all__ = [
    "CorpusEntry",
    "EntryError",
    "Retriever",
    "SnapshotReport",
    "load_snapshot",
    "load_snapshot_report",
]
