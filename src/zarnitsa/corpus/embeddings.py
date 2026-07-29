"""Optional dense retrieval, fused with BM25 by reciprocal rank.

**Off by default, and that is a considered position, not an oversight.**

At 37 entries with consistent domain vocabulary, BM25 already retrieves well (see the
scores in docs/operations.md). Turning this on costs a ~500MB model download, several
hundred MB of resident memory, and multi-second cold starts — none of which Render's
free tier has spare — in exchange for a gain that is hard to measure at this corpus
size. The honest reason to enable it is a corpus large enough that vocabulary mismatch
starts costing recall: a user asking about "escalation thresholds" when the entry says
"conditions for employment" is the case BM25 cannot solve and embeddings can.

Rough guidance: below ~100 entries, leave it off. Past a few hundred, turn it on and
measure. The switch exists so that decision is a config change rather than a rewrite.

Fusion is reciprocal rank (RRF) rather than weighted score blending. BM25 scores are
unbounded and corpus-dependent while cosine similarities sit in [-1, 1]; combining
them numerically requires a normalisation that has to be retuned whenever the corpus
changes. RRF only uses rank position, so it needs no tuning and degrades gracefully
when one retriever is confidently wrong.

Model choice matters here: the corpus is Russian-heavy, so a multilingual encoder is
required. An English-only model will quietly return near-random neighbours on Cyrillic
text rather than failing loudly.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from zarnitsa.corpus.entry import CorpusEntry

log = logging.getLogger(__name__)

# RRF constant. 60 comes from the original paper, where it was tuned against TREC-scale
# result lists of thousands of documents. At that scale it usefully damps the
# difference between adjacent ranks; over a few dozen entries it damps almost all of
# it, and fusion degenerates toward "appears in both lists" rather than "ranked well by
# both". That is still the property worth having here — membership agreement is the
# robust signal — but if you enable hybrid on a corpus this small and find the ordering
# uninformative, lower k rather than concluding fusion doesn't work.
_RRF_K = 60


class EmbeddingIndex:
    """Dense index over corpus entries. Built lazily on first use."""

    def __init__(self, entries: list[CorpusEntry], model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "Hybrid retrieval needs sentence-transformers. "
                'Install with: pip install -e ".[offline]"'
            ) from e

        self.entries = entries
        self.model = SentenceTransformer(model_name)
        # Title + keywords + a content prefix. Embedding the full body of a 615-line
        # entry dilutes the vector toward the document's average topic, which is
        # exactly the wrong representation for retrieval.
        payloads = [
            f"{e.title}\n{' '.join(e.keywords)}\n{e.content[:2000]}" for e in entries
        ]
        self.vectors = self.model.encode(
            payloads, normalize_embeddings=True, show_progress_bar=False
        )
        log.info("Embedding index built: %d entries, model=%s", len(entries), model_name)

    def rank(self, query: str) -> list[int]:
        """Return entry indices ordered by cosine similarity, best first."""
        q = self.model.encode([query], normalize_embeddings=True)[0]
        scores = self.vectors @ q  # normalised, so dot product is cosine
        return sorted(range(len(scores)), key=lambda i: float(scores[i]), reverse=True)


def reciprocal_rank_fusion(
    rankings: list[list[int]],
    *,
    k: int = _RRF_K,
) -> dict[int, float]:
    """Fuse several rankings of the same items into one score per item.

    Each ranking contributes 1/(k + rank). An item ranked highly by either retriever
    scores well; an item ranked highly by both scores best.
    """
    fused: dict[int, float] = {}
    for ranking in rankings:
        for rank, idx in enumerate(ranking):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return fused


def fuse(
    bm25_ranking: list[int],
    dense_ranking: list[int],
    top_k: int,
) -> list[tuple[int, float]]:
    """Fuse BM25 and dense rankings, returning (index, fused_score) best-first."""
    fused = reciprocal_rank_fusion([bm25_ranking, dense_ranking])
    ordered = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
    return ordered[:top_k]


def build_index(entries: list[CorpusEntry], model_name: str) -> Any:
    """Construct an EmbeddingIndex, or return None if the optional deps are missing.

    Returning None rather than raising means a misconfigured hybrid setup degrades to
    BM25-only with a warning, instead of taking retrieval down entirely — which is the
    failure mode this whole PR exists to prevent.
    """
    try:
        return EmbeddingIndex(entries, model_name)
    except Exception:
        log.exception(
            "Embedding index unavailable — falling back to BM25-only retrieval"
        )
        return None
