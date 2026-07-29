"""Retrieval tests.

The regression guard that matters most here is `test_every_corpus_entry_parses`.
Five entries shipped with unparseable YAML frontmatter, and because `load_snapshot`
raises on the first bad file while the orchestrator caught the exception and
continued, every deliberation silently ran with no corpus grounding at all. A test
that merely asserts "some entries load" would not have caught it; this one asserts
the whole snapshot parses.
"""

from __future__ import annotations

from datetime import date

import pytest

from zarnitsa.corpus import CorpusEntry, Retriever, load_snapshot
from zarnitsa.corpus.entry import snapshot_dir
from zarnitsa.corpus.retrieval import tokenize
from zarnitsa.types import SourceTier


@pytest.fixture(scope="module")
def retriever() -> Retriever:
    return Retriever()


def _entry(**kw: object) -> CorpusEntry:
    base = {
        "id": "e1",
        "title": "t",
        "tier": SourceTier.PRIMARY_DOCTRINE,
        "content": "c",
    }
    return CorpusEntry(**{**base, **kw})  # type: ignore[arg-type]


def _filler(n: int = 12) -> list[CorpusEntry]:
    """Distractor documents sharing no vocabulary with the entries under test.

    BM25 IDF is only meaningful relative to a corpus. In a two-document corpus where
    both documents contain the query term, IDF goes non-positive and rank_bm25's
    epsilon floor can't rescue it, so everything scores zero. That is a property of
    the fixture, not of the retriever — the real 37-entry corpus has no non-positive
    IDF terms — so tests that care about ranking pad the corpus to a realistic size.
    """
    return [
        _entry(id=f"filler{i}", content=f"unrelated administrative memorandum {i}")
        for i in range(n)
    ]


# --- corpus integrity ------------------------------------------------------


def test_every_corpus_entry_parses() -> None:
    """Every .md in the snapshot must load. One bad file takes the corpus offline."""
    files = sorted(snapshot_dir().glob("*.md"))
    assert files, "snapshot directory is empty"
    entries = load_snapshot()
    # README.md has no `tier` and is skipped by design; everything else must load.
    assert len(entries) >= len(files) - 1


def test_corpus_is_not_empty(retriever: Retriever) -> None:
    assert len(retriever) > 20, "corpus unexpectedly small — did the snapshot path move?"


def test_entry_ids_are_unique() -> None:
    ids = [e.id for e in load_snapshot()]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"duplicate entry ids break citation matching: {duplicates}"


def test_empty_source_date_coerces_to_none() -> None:
    assert _entry(source_date="").source_date is None
    assert _entry(source_date="2014-12-26").source_date == date(2014, 12, 26)


def test_null_list_fields_coerce_to_empty() -> None:
    assert _entry(keywords=None, topics=None).keywords == []


# --- tokenizer -------------------------------------------------------------


def test_tokenizer_handles_cyrillic() -> None:
    assert "ядерн" in tokenize("ядерное")
    assert "ядерн" in tokenize("ядерных")


def test_tokenizer_drops_single_chars() -> None:
    assert tokenize("a в the") == ["the"]


def test_stemming_is_length_guarded() -> None:
    """Short words must not be stemmed into nothing."""
    assert tokenize("ось") == ["ось"]


# --- ranking ---------------------------------------------------------------


def test_search_returns_relevant_entry_first(retriever: Retriever) -> None:
    hits = retriever.search("nuclear deterrence", top_k=3)
    assert hits, "no hits for a topic the corpus definitely covers"
    assert "nuclear" in hits[0][0].id


def test_search_matches_cyrillic_query(retriever: Retriever) -> None:
    hits = retriever.search("ядерное сдерживание", top_k=3)
    assert hits, "Cyrillic query returned nothing"
    assert any("nuclear" in e.id for e, _ in hits)


def test_search_respects_top_k(retriever: Retriever) -> None:
    assert len(retriever.search("doctrine", top_k=2)) <= 2


def test_scores_are_descending(retriever: Retriever) -> None:
    scores = [s for _, s in retriever.search("military doctrine threat", top_k=6)]
    assert scores == sorted(scores, reverse=True)


def test_zero_score_entries_are_dropped(retriever: Retriever) -> None:
    assert all(s > 0 for _, s in retriever.search("doctrine", top_k=50))


def test_nonsense_query_returns_nothing(retriever: Retriever) -> None:
    assert retriever.search("zzzqqqxxwv", top_k=5) == []


def test_empty_query_returns_nothing(retriever: Retriever) -> None:
    assert retriever.search("", top_k=5) == []


def test_tier_floor_filters_low_tiers() -> None:
    entries = [
        _entry(id="high", tier=SourceTier.PRIMARY_DOCTRINE, content="nuclear doctrine"),
        _entry(id="low", tier=SourceTier.OSINT_ANALYSIS, content="nuclear doctrine"),
        *_filler(),
    ]
    r = Retriever(entries)
    unfiltered = {e.id for e, _ in r.search("nuclear")}
    assert unfiltered == {"high", "low"}, "both should match without a floor"
    filtered = {e.id for e, _ in r.search("nuclear", tier_floor=SourceTier.KREMLIN_STATEMENT)}
    assert filtered == {"high"}


def test_empty_corpus_does_not_explode() -> None:
    """BM25Okapi raises on an empty corpus; the guard must degrade to no results."""
    assert Retriever([]).search("anything") == []


def test_length_normalisation_beats_raw_frequency() -> None:
    """A short on-topic entry should outrank a long entry that merely mentions the term.

    This is the specific failure of the previous substring scorer, which summed raw
    hits and therefore always favoured the longest document.
    """
    entries = [
        _entry(id="short", content="Reflexive control is the doctrine."),
        _entry(
            id="long",
            content="Procurement schedule appendix. " * 400
            + "reflexive control "
            + "Procurement schedule appendix. " * 400,
        ),
        *_filler(),
    ]
    hits = Retriever(entries).search("reflexive control")
    ranked = [e.id for e, _ in hits]
    assert ranked[:2] == ["short", "long"], f"length normalisation failed: {ranked}"
