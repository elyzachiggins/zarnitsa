"""Citation-extraction tests.

These guard the provenance claim in the README: that persona output is linked back to
corpus sources. Before this module existed, `PersonaTurn.citations` was `[]` on every
turn ever produced and the frontend's citation rendering had nothing to display.
"""

from __future__ import annotations

from zarnitsa.corpus import CorpusEntry
from zarnitsa.provenance import citation_coverage, extract_citations
from zarnitsa.types import SourceTier


def _entry(entry_id: str, content: str = "body text", **kw: object) -> CorpusEntry:
    base = {
        "id": entry_id,
        "title": f"Title {entry_id}",
        "tier": SourceTier.PRIMARY_DOCTRINE,
        "content": content,
    }
    return CorpusEntry(**{**base, **kw})  # type: ignore[arg-type]


def _retrieved(*ids: str) -> list[tuple[CorpusEntry, float]]:
    return [(_entry(i), 1.0) for i in ids]


def test_extracts_id_from_bracketed_header() -> None:
    text = "As established in [PRIMARY_DOCTRINE | military_doctrine_2014], the threat is external."
    cites = extract_citations(text, _retrieved("military_doctrine_2014"))
    assert [c.entry_id for c in cites] == ["military_doctrine_2014"]


def test_extracts_bare_inline_id() -> None:
    cites = extract_citations(
        "Per military_doctrine_2014 the assessment holds.",
        _retrieved("military_doctrine_2014"),
    )
    assert len(cites) == 1


def test_ignores_ids_that_were_not_retrieved() -> None:
    """A persona cannot manufacture provenance by inventing a plausible id."""
    cites = extract_citations(
        "According to totally_invented_entry_2019, this is doctrine.",
        _retrieved("military_doctrine_2014"),
    )
    assert cites == []


def test_deduplicates_repeated_citations() -> None:
    text = "military_doctrine_2014 says X. Again, military_doctrine_2014 says Y."
    assert len(extract_citations(text, _retrieved("military_doctrine_2014"))) == 1


def test_preserves_order_of_first_appearance() -> None:
    text = "First svo_causes_nato_expansion, then military_doctrine_2014."
    cites = extract_citations(
        text, _retrieved("military_doctrine_2014", "svo_causes_nato_expansion")
    )
    assert [c.entry_id for c in cites] == [
        "svo_causes_nato_expansion",
        "military_doctrine_2014",
    ]


def test_longer_id_wins_over_prefix() -> None:
    """`svo_causes` must not shadow `svo_causes_donbas_2014_2022`."""
    cites = extract_citations(
        "See svo_causes_donbas_2014_2022 for detail.",
        _retrieved("svo_causes", "svo_causes_donbas_2014_2022"),
    )
    assert [c.entry_id for c in cites] == ["svo_causes_donbas_2014_2022"]


def test_does_not_match_inside_a_longer_token() -> None:
    """A substring occurrence is not a citation."""
    cites = extract_citations(
        "The prefix xxmilitary_doctrine_2014xx is not a citation.",
        _retrieved("military_doctrine_2014"),
    )
    assert cites == []


def test_carries_tier_and_snippet_through() -> None:
    entry = _entry("e1", content="Doctrinal body text here.", tier=SourceTier.KREMLIN_STATEMENT)
    cites = extract_citations("cite e1 here", [(entry, 1.0)])
    assert cites[0].tier == SourceTier.KREMLIN_STATEMENT
    assert "Doctrinal body text" in cites[0].snippet


def test_snippet_is_truncated() -> None:
    cites = extract_citations("e1", [(_entry("e1", content="x" * 5000), 1.0)])
    assert len(cites[0].snippet) <= 241
    assert cites[0].snippet.endswith("…")


def test_empty_inputs_are_safe() -> None:
    assert extract_citations("", _retrieved("a")) == []
    assert extract_citations("text", []) == []


def test_coverage_fraction() -> None:
    retrieved = _retrieved("a", "b", "c", "d")
    cites = extract_citations("mentions a and c", retrieved)
    assert citation_coverage(cites, retrieved) == 0.5


def test_coverage_of_empty_retrieval_is_zero() -> None:
    assert citation_coverage([], []) == 0.0
