"""Hybrid retrieval over the corpus — BM25 over stemmed tokens, with field boosts.

Replaces the original substring-overlap scorer, which had three problems that
mattered at this corpus size:

1. No IDF. Every matching term counted the same, so a hit on "the" scored like a hit
   on "рефлексивное".
2. No length normalisation. `sum(1 for t in tokens if t in content)` rewarded long
   entries purely for being long — the 615-line UAV strategy draft outranked short,
   precisely-relevant doctrine articles on almost any query.
3. Substring matching. `"war" in content` matched "warehouse" and "forward"; in
   Cyrillic it matched across morpheme boundaries more or less at random.

BM25 fixes 1 and 2 directly. For 3, tokens are matched whole after a light
suffix-stripping stemmer, which also buys crude Russian morphology — so a query for
"ядерное" reaches an entry that only says "ядерных".

This is deliberately not embeddings. At 38 entries a vector index adds a model
download, RAM, and cold-start latency that Render's free tier does not have, for a
gain that BM25 mostly already captures on a domain-specific corpus with consistent
vocabulary. Revisit if the corpus grows past a few hundred entries.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from rank_bm25 import BM25Okapi

from zarnitsa.config import settings
from zarnitsa.corpus.entry import CorpusEntry, EntryError, load_snapshot_report
from zarnitsa.types import SourceTier

# Unicode-aware: \w includes Cyrillic under Python's default re.UNICODE.
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)

# Inflectional endings, longest first so "ого" strips before "о".
_RU_SUFFIXES = (
    "иями", "ями", "ами", "иях", "ых", "их", "ого", "ему", "ому", "ыми", "ими",
    "ая", "яя", "ое", "ее", "ые", "ие", "ый", "ий", "ой", "ей", "ам", "ям",
    "ах", "ях", "ов", "ев", "ии", "ью", "ия", "ие",
    "а", "я", "о", "е", "ы", "и", "у", "ю", "ь",
)
_EN_SUFFIXES = ("ing", "ies", "es", "ed", "s")

_MIN_STEM = 4

# Weight applied by repeating a field's tokens in the indexed document. BM25 has no
# native field weighting, so duplication is the standard workaround.
_TITLE_WEIGHT = 3
_KEYWORD_WEIGHT = 3
_TOPIC_WEIGHT = 2

_TIER_RANK = {
    SourceTier.PRIMARY_DOCTRINE: 7,
    SourceTier.KREMLIN_STATEMENT: 6,
    SourceTier.ACADEMIC_RUSSIAN: 5,
    SourceTier.RUSSIAN_STATE_MEDIA: 4,
    SourceTier.RUSSIAN_MILBLOGGER: 3,
    SourceTier.OSINT_ANALYSIS: 2,
    SourceTier.MODEL_EXTRAPOLATION: 1,
}


def _stem(token: str) -> str:
    """Strip one inflectional suffix. Crude on purpose — see module docstring."""
    for suffixes in (_RU_SUFFIXES, _EN_SUFFIXES):
        for suf in suffixes:
            if len(token) - len(suf) >= _MIN_STEM and token.endswith(suf):
                return token[: -len(suf)]
    return token


def tokenize(text: str) -> list[str]:
    """Lowercase, split on word boundaries, drop 1-char noise, stem."""
    return [_stem(t) for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1]


def _index_document(entry: CorpusEntry) -> list[str]:
    """Build the token list BM25 indexes for one entry, with field boosts."""
    tokens: list[str] = []
    tokens += tokenize(entry.title) * _TITLE_WEIGHT
    tokens += tokenize(" ".join(entry.keywords)) * _KEYWORD_WEIGHT
    # Topics are English snake_case. `_` is a word character, so \w+ would keep
    # "nuclear_deterrence" as a single token that no natural query ever matches.
    tokens += tokenize(" ".join(entry.topics).replace("_", " ")) * _TOPIC_WEIGHT
    tokens += tokenize(entry.content)
    return tokens


class Retriever:
    """BM25 retrieval over a corpus snapshot.

    The index is built once at construction. `Retriever` is treated as a process-level
    singleton by the orchestrator, so this cost is paid on first request only.
    """

    def __init__(self, entries: Iterable[CorpusEntry] | None = None) -> None:
        if entries is not None:
            self.entries = list(entries)
            self.errors: list[EntryError] = []
        else:
            report = load_snapshot_report()
            self.entries = report.entries
            # Retained rather than logged-and-dropped: a partially-loaded corpus is
            # reported through the API so a caller can tell grounded output from
            # output produced over a corpus that is quietly missing entries.
            self.errors = report.errors
        self._docs = [_index_document(e) for e in self.entries]
        # BM25Okapi raises on an empty corpus; guard so an empty snapshot degrades to
        # "no results" rather than blowing up every request.
        self._bm25 = BM25Okapi(self._docs) if self._docs else None
        # Dense index is opt-in; see corpus/embeddings.py for why it's off by default.
        self._dense = None
        if settings.retrieval_mode == "hybrid" and self.entries:
            from zarnitsa.corpus.embeddings import build_index

            self._dense = build_index(self.entries, settings.embedding_model)

    def __len__(self) -> int:
        return len(self.entries)

    def search(
        self,
        query: str,
        *,
        top_k: int = 8,
        tier_floor: SourceTier | None = None,
    ) -> list[tuple[CorpusEntry, float]]:
        """Return up to `top_k` (entry, score) pairs ranked by BM25, best first.

        Entries scoring zero are dropped rather than padded in — an irrelevant entry
        in the prompt is worse than a shorter prompt, because the persona will try to
        ground its reasoning in it.
        """
        if self._bm25 is None:
            return []
        tokens = tokenize(query)
        if not tokens:
            return []

        scores = self._bm25.get_scores(tokens)
        floor = _TIER_RANK[tier_floor] if tier_floor else None

        def allowed(idx: int) -> bool:
            return floor is None or _TIER_RANK[self.entries[idx].tier] >= floor

        if self._dense is not None:
            # Hybrid: fuse BM25 and dense rankings by reciprocal rank. Keep only
            # entries BM25 gave a positive score, so an irrelevant entry can't be
            # dragged in on dense similarity alone.
            from zarnitsa.corpus.embeddings import fuse

            bm25_ranking = [
                i
                for i in sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
                if scores[i] > 0 and allowed(i)
            ]
            dense_ranking = [i for i in self._dense.rank(query) if allowed(i)]
            positive = set(bm25_ranking)
            dense_ranking = [i for i in dense_ranking if i in positive]
            return [
                (self.entries[i], float(score))
                for i, score in fuse(bm25_ranking, dense_ranking, top_k)
            ]

        scored: list[tuple[CorpusEntry, float]] = []
        for idx, (entry, score) in enumerate(zip(self.entries, scores, strict=True)):
            if score <= 0 or not allowed(idx):
                continue
            scored.append((entry, float(score)))

        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _tier_rank(tier: SourceTier) -> int:
        return _TIER_RANK[tier]
