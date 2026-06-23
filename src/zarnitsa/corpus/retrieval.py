"""Hybrid retrieval over corpus — keyword + (future) vector."""

from __future__ import annotations

from collections.abc import Iterable

from zarnitsa.corpus.entry import CorpusEntry, load_snapshot
from zarnitsa.types import SourceTier


class Retriever:
    """Initial implementation: keyword overlap. Vector retrieval is a TODO."""

    def __init__(self, entries: Iterable[CorpusEntry] | None = None) -> None:
        self.entries: list[CorpusEntry] = list(entries) if entries is not None else load_snapshot()

    def search(
        self,
        query: str,
        *,
        top_k: int = 8,
        tier_floor: SourceTier | None = None,
    ) -> list[tuple[CorpusEntry, float]]:
        """Return entries ranked by simple keyword overlap.

        Replace with embedding-based hybrid retrieval in a follow-up.
        """
        tokens = {t.lower() for t in query.split() if len(t) > 2}
        scored: list[tuple[CorpusEntry, float]] = []
        for e in self.entries:
            if tier_floor and self._tier_rank(e.tier) < self._tier_rank(tier_floor):
                continue
            # Keyword overlap (Russian keywords in corpus)
            overlap = len(tokens & {kw.lower() for kw in e.keywords})
            # Content hits (any language)
            content_hits = sum(1 for t in tokens if t in e.content.lower())
            # Topic hits — topics are English snake_case (e.g. "nuclear_deterrence")
            # Check if any query token is a substring of any topic string
            topic_hits = sum(
                1 for t in tokens
                if any(t in topic.lower() for topic in e.topics)
            )
            # Title hits — English titles for Russian-content entries
            title_hits = sum(1 for t in tokens if t in e.title.lower())
            score = overlap * 2 + content_hits + topic_hits * 2 + title_hits
            if score > 0:
                scored.append((e, float(score)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _tier_rank(tier: SourceTier) -> int:
        order = {
            SourceTier.PRIMARY_DOCTRINE: 7,
            SourceTier.KREMLIN_STATEMENT: 6,
            SourceTier.ACADEMIC_RUSSIAN: 5,
            SourceTier.RUSSIAN_STATE_MEDIA: 4,
            SourceTier.RUSSIAN_MILBLOGGER: 3,
            SourceTier.OSINT_ANALYSIS: 2,
            SourceTier.MODEL_EXTRAPOLATION: 1,
        }
        return order[tier]
