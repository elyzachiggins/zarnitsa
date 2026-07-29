"""Claim-level verification — does the cited entry actually support the claim?

`extract_citations` establishes that a persona named a corpus entry that was genuinely
in its context. That rules out invented sources, but it does not establish that the
entry says anything resembling the sentence it is attached to. A persona can cite a
real entry for a claim that entry does not support, and the citation tag renders
identically either way.

This module closes some of that gap. It is important to be precise about how much.

**Two verifiers, with very different strength:**

`lexical` (default, free, deterministic)
    Content-word overlap between the claim sentence and the cited entry, over the same
    stemmed tokens retrieval uses. This is a *screen*, not a proof. It reliably catches
    the common failure — a claim that shares essentially no vocabulary with the source
    it cites — and it cannot catch a claim that borrows the source's vocabulary while
    misrepresenting what the source says. Treat a low score as "look at this" and a
    high score as "nothing obviously wrong", never as "verified".

`model` (opt-in, costs money)
    Asks a model whether the entry supports the claim. Strictly better at semantics,
    and strictly a judgement made by another language model — which is the thing the
    whole project is trying to be careful about. Use it as evidence, not proof, and
    prefer a different model from the one that produced the claim.

Neither is entailment checking in the formal sense. Presenting either as "verified
provenance" would overclaim. What they give you is a ranked list of citations most
likely to be wrong, which is what makes manual review tractable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from zarnitsa.corpus.entry import CorpusEntry
from zarnitsa.corpus.retrieval import tokenize
from zarnitsa.types import Citation

# Sentence split on terminal punctuation followed by whitespace + capital/Cyrillic.
# Deliberately simple; over-splitting costs a little precision, not correctness.
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁ])")

# Tokens too common to carry evidential weight in either language.
_STOPWORDS = frozenset(
    tokenize(
        "the a an and or but if then than that this these those of in on at to for "
        "with from by as is are was were be been being it its their his her our your "
        "we they he she you i not no nor so such may might must can could would should "
        "will shall have has had do does did which who whom whose what when where why how "
        "и в на с по для от до за из к о об при не но а или что как это тот та то те "
        "был была было были быть есть же бы ли уже еще их его ее наш ваш"
    )
)

_MIN_CLAIM_TOKENS = 4

# Fraction of alphabetic characters that must be Cyrillic for text to count as Russian.
_CYRILLIC_AT = 0.35
_CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
_ALPHA_RE = re.compile(r"[^\W\d_]", re.UNICODE)


def _is_cyrillic(text: str) -> bool:
    alpha = len(_ALPHA_RE.findall(text))
    if not alpha:
        return False
    return len(_CYRILLIC_RE.findall(text)) / alpha >= _CYRILLIC_AT


def _comparable(claim: str, entry: CorpusEntry) -> bool:
    """Is a lexical comparison between this claim and this entry meaningful at all?

    It is not, when they are written in different scripts. Zarnitsa's language rule
    makes personas write in English, while most corpus entries are Russian source
    text — so word overlap between an English claim and a Cyrillic body is near zero
    whether or not the entry supports the claim.

    Scoring those pairs anyway would mark almost every citation UNSUPPORTED and make
    the screen worse than useless: a flag that fires on everything is a flag nobody
    reads. Such pairs are reported as NOT_ASSESSED instead, and excluded from the
    support rate. Cross-lingual claim checking needs the multilingual embedding path
    (ZARNITSA_RETRIEVAL_MODE=hybrid), not word overlap.
    """
    entry_text = f"{entry.title} {entry.content[:1500]}"
    return _is_cyrillic(claim) == _is_cyrillic(entry_text)


class SupportLevel(str, Enum):
    SUPPORTED = "supported"
    WEAK = "weak"
    UNSUPPORTED = "unsupported"
    NOT_ASSESSED = "not_assessed"


@dataclass
class ClaimCheck:
    """One cited sentence, checked against one entry it cites."""

    claim: str
    entry_id: str
    score: float
    level: SupportLevel
    method: str = "lexical"
    overlap_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "claim": self.claim,
            "entry_id": self.entry_id,
            "score": round(self.score, 3),
            "level": self.level.value,
            "method": self.method,
            "overlap_terms": self.overlap_terms[:12],
        }


# Thresholds are conservative on purpose: this is a screen, so it should over-flag
# rather than wave through. Tune against your own corpus before trusting them.
_SUPPORTED_AT = 0.45
_WEAK_AT = 0.20


def split_claims(text: str) -> list[str]:
    """Split prose into candidate claim sentences, dropping headings and list markers."""
    claims: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("---"):
            continue
        line = re.sub(r"^[-*•]\s*", "", line)
        for sentence in _SENTENCE_RE.split(line):
            s = sentence.strip()
            if len(s) > 20:
                claims.append(s)
    return claims


def _content_tokens(text: str) -> set[str]:
    return {t for t in tokenize(text) if t not in _STOPWORDS}


def lexical_support(claim: str, entry: CorpusEntry) -> tuple[float, list[str]]:
    """Fraction of the claim's content words that appear in the entry.

    Returns (score, overlapping terms). Scores the claim against the entry's full text
    plus its title and keywords, since a doctrinal entry often states in its title what
    the body assumes.
    """
    claim_tokens = _content_tokens(claim)
    if len(claim_tokens) < _MIN_CLAIM_TOKENS:
        return 0.0, []
    entry_tokens = _content_tokens(
        f"{entry.title} {' '.join(entry.keywords)} {entry.content}"
    )
    overlap = claim_tokens & entry_tokens
    return len(overlap) / len(claim_tokens), sorted(overlap)


def _level(score: float) -> SupportLevel:
    if score >= _SUPPORTED_AT:
        return SupportLevel.SUPPORTED
    if score >= _WEAK_AT:
        return SupportLevel.WEAK
    return SupportLevel.UNSUPPORTED


def verify_turn(
    text: str,
    citations: list[Citation],
    retrieved: list[tuple[CorpusEntry, float]],
) -> list[ClaimCheck]:
    """Check every sentence that names a cited entry against that entry.

    Only sentences that explicitly carry an entry_id are checked — attributing an
    unmarked sentence to a nearby citation would be guessing at which claim the
    persona meant to attach it to.
    """
    if not citations or not retrieved:
        return []

    by_id = {e.id: e for e, _ in retrieved}
    cited_ids = [c.entry_id for c in citations if c.entry_id in by_id]
    if not cited_ids:
        return []

    checks: list[ClaimCheck] = []
    for claim in split_claims(text):
        for entry_id in cited_ids:
            if entry_id not in claim:
                continue
            # Strip the citation marker so the id's own tokens don't inflate overlap.
            cleaned = claim.replace(entry_id, " ")
            entry = by_id[entry_id]

            if not _comparable(cleaned, entry):
                checks.append(
                    ClaimCheck(
                        claim=cleaned.strip(),
                        entry_id=entry_id,
                        score=0.0,
                        level=SupportLevel.NOT_ASSESSED,
                        method="lexical/skipped-cross-script",
                    )
                )
                continue

            score, overlap = lexical_support(cleaned, entry)
            checks.append(
                ClaimCheck(
                    claim=cleaned.strip(),
                    entry_id=entry_id,
                    score=score,
                    level=_level(score),
                    overlap_terms=overlap,
                )
            )
    return checks


@dataclass
class VerificationSummary:
    checks: list[ClaimCheck]

    @property
    def assessed(self) -> list[ClaimCheck]:
        """Only claims the screen could actually evaluate."""
        return [c for c in self.checks if c.level is not SupportLevel.NOT_ASSESSED]

    @property
    def skipped(self) -> list[ClaimCheck]:
        return [c for c in self.checks if c.level is SupportLevel.NOT_ASSESSED]

    @property
    def unsupported(self) -> list[ClaimCheck]:
        return [c for c in self.checks if c.level is SupportLevel.UNSUPPORTED]

    @property
    def support_rate(self) -> float | None:
        """Fraction of *assessable* claims that cleared the SUPPORTED threshold.

        None when nothing could be assessed — which on a Russian-source corpus with
        English personas is the common case. Returning 0.0 there would read as "no
        claims were supported" when the truth is "no claim was checked".
        """
        assessed = self.assessed
        if not assessed:
            return None
        strong = sum(1 for c in assessed if c.level is SupportLevel.SUPPORTED)
        return strong / len(assessed)

    def to_dict(self) -> dict[str, object]:
        rate = self.support_rate
        caveat = (
            "Lexical overlap is a screen, not proof of entailment. A low score flags a "
            "citation worth reviewing; a high score does not establish that the source "
            "supports the claim."
        )
        if self.skipped:
            caveat += (
                f" {len(self.skipped)} claim(s) were NOT assessed because the claim and "
                "the cited entry are in different scripts — word overlap is meaningless "
                "across languages. Cross-lingual checking needs the embedding path."
            )
        return {
            "method": "lexical",
            "assessed_claims": len(self.assessed),
            "skipped_claims": len(self.skipped),
            "support_rate": round(rate, 3) if rate is not None else None,
            "unsupported": [c.to_dict() for c in self.unsupported[:10]],
            "caveat": caveat,
        }


def summarise(checks: list[ClaimCheck]) -> VerificationSummary:
    return VerificationSummary(checks=checks)
