"""Claim-verification tests.

These check the screen behaves as advertised. They deliberately do NOT assert that it
detects semantic misattribution — it can't, and a test implying otherwise would
encode the overclaim the module docstring warns against.
"""

from __future__ import annotations

from zarnitsa.corpus import CorpusEntry
from zarnitsa.provenance import SupportLevel, summarise, verify_turn
from zarnitsa.provenance.verify import lexical_support, split_claims
from zarnitsa.types import Citation, SourceTier

DOCTRINE = (
    "Strategic deterrence encompasses nuclear and non-nuclear means. The Basic "
    "Principles define four conditions for nuclear employment, including ballistic "
    "missile attack on Russian territory and conventional aggression threatening the "
    "existence of the state."
)


def _entry(entry_id: str = "nuke_doc", content: str = DOCTRINE) -> CorpusEntry:
    return CorpusEntry(
        id=entry_id,
        title="Nuclear Deterrence Basics",
        tier=SourceTier.PRIMARY_DOCTRINE,
        content=content,
    )


def _cite(entry_id: str = "nuke_doc") -> Citation:
    return Citation(entry_id=entry_id, tier=SourceTier.PRIMARY_DOCTRINE)


# --- sentence splitting ----------------------------------------------------


def test_split_drops_headings_and_bullets() -> None:
    text = "# Assessment\n- Short\nStrategic deterrence covers nuclear means today."
    claims = split_claims(text)
    assert not any(c.startswith("#") for c in claims)
    assert any("Strategic deterrence" in c for c in claims)


def test_split_separates_sentences() -> None:
    text = "The first claim is long enough to count. The second claim is also long."
    assert len(split_claims(text)) == 2


# --- lexical support -------------------------------------------------------


def test_supported_claim_scores_high() -> None:
    claim = "Strategic deterrence encompasses nuclear and non-nuclear means."
    score, overlap = lexical_support(claim, _entry())
    assert score > 0.6
    assert "nuclear" in overlap


def test_unrelated_claim_scores_low() -> None:
    claim = "Baltic fishing quotas were renegotiated with Finland last spring."
    score, _ = lexical_support(claim, _entry())
    assert score < 0.2


def test_stopwords_do_not_inflate_score() -> None:
    claim = "The and or but if then than that this these those of in on at to for."
    score, _ = lexical_support(claim, _entry())
    assert score == 0.0, "a sentence of pure stopwords must not count as supported"


def test_very_short_claims_are_not_scored() -> None:
    assert lexical_support("It is so.", _entry()) == (0.0, [])


def test_cyrillic_claim_matches_cyrillic_source() -> None:
    entry = _entry(content="Ядерное сдерживание охватывает ядерные и неядерные средства.")
    score, _ = lexical_support("Ядерное сдерживание охватывает неядерные средства", entry)
    assert score > 0.5


# --- turn verification -----------------------------------------------------


def test_verifies_only_sentences_carrying_a_citation() -> None:
    text = (
        "Strategic deterrence encompasses nuclear and non-nuclear means nuke_doc. "
        "Baltic fishing quotas were renegotiated with Finland last spring."
    )
    checks = verify_turn(text, [_cite()], [(_entry(), 1.0)])
    assert len(checks) == 1
    assert "Strategic deterrence" in checks[0].claim


def test_citation_id_is_stripped_before_scoring() -> None:
    """The id's own tokens must not count as evidence for the claim."""
    checks = verify_turn(
        "Strategic deterrence encompasses nuclear means nuke_doc.",
        [_cite()],
        [(_entry(), 1.0)],
    )
    assert "nuke_doc" not in checks[0].claim


def test_unsupported_claim_is_flagged() -> None:
    text = "Baltic fishing quotas were renegotiated with Finland last spring nuke_doc."
    checks = verify_turn(text, [_cite()], [(_entry(), 1.0)])
    assert checks[0].level is SupportLevel.UNSUPPORTED


def test_supported_claim_is_marked_supported() -> None:
    text = "Strategic deterrence encompasses nuclear and non-nuclear means nuke_doc."
    checks = verify_turn(text, [_cite()], [(_entry(), 1.0)])
    assert checks[0].level is SupportLevel.SUPPORTED


def test_no_citations_means_no_checks() -> None:
    assert verify_turn("Some prose.", [], [(_entry(), 1.0)]) == []


# --- summary ---------------------------------------------------------------


def test_summary_reports_rate_and_unsupported() -> None:
    text = (
        "Strategic deterrence encompasses nuclear and non-nuclear means nuke_doc. "
        "Baltic fishing quotas were renegotiated with Finland last spring nuke_doc."
    )
    summary = summarise(verify_turn(text, [_cite()], [(_entry(), 1.0)]))
    assert len(summary.assessed) == 2
    assert summary.support_rate == 0.5
    assert len(summary.unsupported) == 1


def test_summary_carries_the_caveat() -> None:
    """The dict must never present this as proof of entailment."""
    d = summarise([]).to_dict()
    assert "not proof of entailment" in d["caveat"]


# --- cross-script handling -------------------------------------------------


def test_english_claim_against_russian_entry_is_not_assessed() -> None:
    """The dominant case for this corpus: English personas, Russian source text.

    Word overlap across scripts is near zero whether or not the entry supports the
    claim, so scoring it would flag essentially every citation. Must be reported as
    NOT_ASSESSED, never UNSUPPORTED.
    """
    russian = _entry(content="Ядерное сдерживание охватывает ядерные и неядерные средства.")
    checks = verify_turn(
        "Strategic deterrence encompasses nuclear and non-nuclear means nuke_doc.",
        [_cite()],
        [(russian, 1.0)],
    )
    assert checks[0].level is SupportLevel.NOT_ASSESSED
    assert "cross-script" in checks[0].method


def test_same_script_pairs_are_still_assessed() -> None:
    checks = verify_turn(
        "Strategic deterrence encompasses nuclear and non-nuclear means nuke_doc.",
        [_cite()],
        [(_entry(), 1.0)],
    )
    assert checks[0].level is SupportLevel.SUPPORTED


def test_support_rate_is_none_when_nothing_assessable() -> None:
    """None, not 0.0 — 'nothing was checked' is not 'nothing was supported'."""
    russian = _entry(content="Ядерное сдерживание охватывает ядерные средства.")
    summary = summarise(
        verify_turn("Strategic deterrence covers nuclear means nuke_doc.", [_cite()],
                    [(russian, 1.0)])
    )
    assert summary.support_rate is None
    assert summary.to_dict()["support_rate"] is None
    assert summary.to_dict()["skipped_claims"] == 1


def test_skipped_claims_are_explained_in_the_caveat() -> None:
    russian = _entry(content="Ядерное сдерживание охватывает ядерные средства.")
    d = summarise(
        verify_turn("Strategic deterrence covers nuclear means nuke_doc.", [_cite()],
                    [(russian, 1.0)])
    ).to_dict()
    assert "different scripts" in d["caveat"]


def test_russian_claim_against_russian_entry_is_assessed() -> None:
    russian = _entry(content="Ядерное сдерживание охватывает ядерные и неядерные средства.")
    checks = verify_turn(
        "Ядерное сдерживание охватывает ядерные и неядерные средства nuke_doc.",
        [_cite()],
        [(russian, 1.0)],
    )
    assert checks[0].level is SupportLevel.SUPPORTED
