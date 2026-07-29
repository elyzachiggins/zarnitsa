"""Recover corpus citations from persona prose.

The council prompt hands each persona a block of retrieved entries stamped with
`[TIER | entry_id]` headers and tells it to reference the entry_id when it cites one.
Personas do this — but nothing was reading those references back out, so
`PersonaTurn.citations` was `[]` on every turn ever produced, and the frontend's
citation-tag rendering had no data to display.

This module closes that loop. It is deliberately match-only: a citation is emitted
only when the persona names an entry_id that was actually retrieved for this turn.
That means a persona cannot manufacture provenance by inventing a plausible-looking
id — an unrecognised id is dropped, not trusted.

What this does NOT do is verify that the cited entry supports the claim it is attached
to. It establishes that a claim points at a real corpus entry that was in context.
Genuine claim-level entailment checking is a much harder problem and should not be
described as if this delivers it.
"""

from __future__ import annotations

import re

from zarnitsa.corpus.entry import CorpusEntry
from zarnitsa.types import Citation

# Longest-match-first alternation is built per call from the retrieved ids, so ids
# that are prefixes of others (e.g. "svo_causes" vs "svo_causes_donbas") resolve to
# the longer one.
_BOUNDARY = r"(?<![A-Za-z0-9_-]){}(?![A-Za-z0-9_-])"

_SNIPPET_CHARS = 240


def _snippet(entry: CorpusEntry) -> str:
    text = " ".join(entry.content.split())
    if len(text) <= _SNIPPET_CHARS:
        return text
    return text[:_SNIPPET_CHARS].rstrip() + "…"


def extract_citations(
    text: str,
    retrieved: list[tuple[CorpusEntry, float]],
) -> list[Citation]:
    """Return citations for every retrieved entry whose id appears in `text`.

    Order follows first appearance in the prose, so the UI lists them in the order the
    persona actually used them. Each entry is emitted at most once.
    """
    if not text or not retrieved:
        return []

    by_id: dict[str, CorpusEntry] = {e.id: e for e, _ in retrieved if e.id}
    if not by_id:
        return []

    # Longest ids first so a prefix id can't shadow a more specific one.
    ordered_ids = sorted(by_id, key=len, reverse=True)
    pattern = re.compile(
        "|".join(_BOUNDARY.format(re.escape(i)) for i in ordered_ids)
    )

    seen: set[str] = set()
    citations: list[Citation] = []
    for match in pattern.finditer(text):
        entry_id = match.group(0)
        if entry_id in seen:
            continue
        seen.add(entry_id)
        entry = by_id[entry_id]
        citations.append(
            Citation(
                entry_id=entry.id,
                tier=entry.tier,
                snippet=_snippet(entry),
                date=entry.source_date.isoformat() if entry.source_date else None,
            )
        )
    return citations


def citation_coverage(
    citations: list[Citation],
    retrieved: list[tuple[CorpusEntry, float]],
) -> float:
    """Fraction of retrieved entries the persona actually cited, in [0.0, 1.0].

    A fidelity signal, not a grade: low coverage can mean the persona ignored its
    grounding, or that retrieval surfaced entries irrelevant to the scenario. Reading
    it alongside the retrieval scores tells you which.
    """
    if not retrieved:
        return 0.0
    return len(citations) / len(retrieved)
