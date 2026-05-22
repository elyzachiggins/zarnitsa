"""Knowledge corpus — doctrine, speeches, lessons-learned, with provenance tags."""

from zarnitsa.corpus.entry import CorpusEntry, load_snapshot
from zarnitsa.corpus.retrieval import Retriever

__all__ = ["CorpusEntry", "load_snapshot", "Retriever"]
