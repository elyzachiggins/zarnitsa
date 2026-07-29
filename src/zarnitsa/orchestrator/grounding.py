"""Grounding status — whether a deliberation actually had corpus material behind it.

This exists because of a specific failure. Five corpus entries shipped with malformed
YAML, `load_snapshot()` aborted on the first one, and `_run_persona` caught the
exception, wrote `log.exception("proceeding without grounding")`, and carried on. Every
deliberation for weeks ran with no source material while producing confident,
well-structured, doctrinally-flavoured output. The API response looked identical to a
grounded one. Nothing a user could see said otherwise.

Repairing the five files fixed that instance. It did not fix the mechanism — the next
malformed entry would have hidden exactly the same way. So grounding status is now a
value that travels with the response:

- CORPUS_UNAVAILABLE  the corpus could not be loaded at all
- NO_MATCH            corpus loaded fine, but nothing matched this scenario
- DEGRADED            some entries failed to load; retrieval ran over a partial corpus
- GROUNDED            full corpus, entries retrieved

NO_MATCH is normal for an obscure scenario and is not an error. CORPUS_UNAVAILABLE is
never normal, and by default the API refuses the request rather than returning
ungrounded analysis that looks grounded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class GroundingStatus(str, Enum):
    GROUNDED = "grounded"
    DEGRADED = "degraded"
    NO_MATCH = "no_match"
    CORPUS_UNAVAILABLE = "corpus_unavailable"


@dataclass
class Grounding:
    status: GroundingStatus
    entry_ids: list[str] = field(default_factory=list)
    corpus_size: int = 0
    corpus_errors: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def is_grounded(self) -> bool:
        """True when at least one corpus entry reached the personas."""
        return self.status in (GroundingStatus.GROUNDED, GroundingStatus.DEGRADED)

    @property
    def warning(self) -> str | None:
        """Human-readable caveat to surface in the UI, or None when fully grounded."""
        if self.status is GroundingStatus.GROUNDED:
            return None
        if self.status is GroundingStatus.CORPUS_UNAVAILABLE:
            return (
                "The doctrine corpus could not be loaded. This analysis has NO source "
                "grounding and should not be treated as corpus-supported."
            )
        if self.status is GroundingStatus.NO_MATCH:
            return (
                "No corpus entries matched this scenario. The council reasoned from its "
                "institutional priors alone, without retrieved source material."
            )
        return (
            f"{len(self.corpus_errors)} corpus entr(y/ies) failed to load; retrieval ran "
            "over a partial corpus. Run `zarnitsa doctor` for details."
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "is_grounded": self.is_grounded,
            "entry_ids": self.entry_ids,
            "corpus_size": self.corpus_size,
            "corpus_errors": self.corpus_errors,
            "warning": self.warning,
            "detail": self.detail,
        }
