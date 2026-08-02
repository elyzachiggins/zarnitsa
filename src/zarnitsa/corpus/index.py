"""Vector index over corpus chunks + hybrid (semantic + keyword) retrieval.

Build once, offline (needs HF_TOKEN):
    PYTHONPATH=src python -m zarnitsa.corpus.index

That writes vectors + chunk metadata into the snapshot's `_index/` folder,
which is committed with the corpus. At runtime the index loads from disk and
only the query is embedded live.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np

from zarnitsa.config import settings
from zarnitsa.corpus.chunker import Chunk, chunk_snapshot
from zarnitsa.corpus.embeddings import embed_query, embed_texts
from zarnitsa.corpus.entry import snapshot_dir
from zarnitsa.types import SourceTier

# Authority ordering: index 0 = highest authority.
_TIER_ORDER = [
    SourceTier.PRIMARY_DOCTRINE,
    SourceTier.KREMLIN_STATEMENT,
    SourceTier.ACADEMIC_RUSSIAN,
    SourceTier.RUSSIAN_STATE_MEDIA,
    SourceTier.RUSSIAN_MILBLOGGER,
    SourceTier.OSINT_ANALYSIS,
    SourceTier.MODEL_EXTRAPOLATION,
]
_TIER_RANK = {t: i for i, t in enumerate(_TIER_ORDER)}
_WORD = re.compile(r"\w+", re.UNICODE)


def _index_dir(snapshot: str | None = None) -> Path:
    return snapshot_dir(snapshot) / "_index"


def build_index(snapshot: str | None = None, *, batch_size: int = 16) -> int:
    """Chunk the snapshot, embed all chunks, and persist the index. Returns count."""
    chunks = chunk_snapshot(snapshot)
    vectors = embed_texts([c.text for c in chunks], batch_size=batch_size)
    d = _index_dir(snapshot)
    d.mkdir(parents=True, exist_ok=True)
    np.save(d / "vectors.npy", vectors)
    (d / "chunks.json").write_text(
        json.dumps([c.model_dump() for c in chunks], ensure_ascii=False),
        encoding="utf-8",
    )
    (d / "meta.json").write_text(
        json.dumps(
            {"model": settings.embedding_model, "count": len(chunks), "dim": int(vectors.shape[1])},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return len(chunks)


class ChunkIndex:
    """In-memory hybrid retriever over precomputed chunk vectors."""

    def __init__(self, vectors: np.ndarray, chunks: list[Chunk]) -> None:
        self.vectors = vectors
        self.chunks = chunks
        self._hay = [f"{c.text}\n{c.anchor}\n{c.title}".lower() for c in chunks]

    @classmethod
    def load(cls, snapshot: str | None = None) -> "ChunkIndex":
        d = _index_dir(snapshot)
        vpath, cpath = d / "vectors.npy", d / "chunks.json"
        if not vpath.exists() or not cpath.exists():
            raise FileNotFoundError(
                f"no vector index at {d} — build it with "
                f"`PYTHONPATH=src python -m zarnitsa.corpus.index`"
            )
        vectors = np.load(vpath)
        chunks = [Chunk(**c) for c in json.loads(cpath.read_text(encoding="utf-8"))]
        return cls(vectors, chunks)

    def _keyword_scores(self, query: str) -> np.ndarray:
        toks = {t.lower() for t in _WORD.findall(query) if len(t) > 2}
        if not toks:
            return np.zeros(len(self.chunks), dtype=np.float32)
        raw = np.array([sum(1 for t in toks if t in hay) for hay in self._hay], dtype=np.float32)
        top = raw.max()
        return raw / top if top > 0 else raw

    def search(
        self,
        query: str,
        *,
        top_k: int = 6,
        persona: str | None = None,
        tier_floor: SourceTier | None = None,
        alpha: float = 0.75,
    ) -> list[tuple[Chunk, float]]:
        """Hybrid search: alpha*cosine + (1-alpha)*keyword, +persona boost.

        `persona` (a PersonaRole value) gently boosts chunks whose source entry
        lists that persona in `cited_by_personas`.
        """
        qv = embed_query(query)
        dense = self.vectors @ qv                       # cosine (vectors are unit-norm)
        keyword = self._keyword_scores(query)
        score = alpha * dense + (1.0 - alpha) * keyword
        if persona:
            boost = np.array(
                [0.05 if persona in c.cited_by_personas else 0.0 for c in self.chunks],
                dtype=np.float32,
            )
            score = score + boost

        results: list[tuple[Chunk, float]] = []
        for i in np.argsort(-score):
            chunk = self.chunks[i]
            if tier_floor is not None and _TIER_RANK[chunk.tier] > _TIER_RANK[tier_floor]:
                continue
            results.append((chunk, float(score[i])))
            if len(results) >= top_k:
                break
        return results


if __name__ == "__main__":
    n = build_index()
    print(f"built index: {n} chunks -> {_index_dir()}")
