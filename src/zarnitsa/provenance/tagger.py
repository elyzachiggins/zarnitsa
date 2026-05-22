"""Provenance tagging — links persona claims back to corpus entries by tier.

Initial implementation: structural — persona outputs a JSON `citations` block alongside
prose; the tagger normalizes it. Later: an enforcement layer that, under
ZARNITSA_FIDELITY_MODE=strict, rejects outputs that fail to cite when making
fact-shaped claims.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from zarnitsa.config import settings
from zarnitsa.exceptions import FidelityViolation
from zarnitsa.types import Citation, SourceTier


class TaggedClaim(BaseModel):
    """A single claim with its provenance trail."""

    text: str
    citations: list[Citation] = Field(default_factory=list)
    tier_floor: SourceTier = SourceTier.MODEL_EXTRAPOLATION


class ProvenanceTagger:
    """Normalize and (in strict mode) enforce citation discipline on outputs."""

    def __init__(self, *, strict: bool | None = None) -> None:
        self.strict = strict if strict is not None else (settings.fidelity_mode == "strict")

    def tag(
        self,
        text: str,
        citations: list[Citation],
        *,
        tier_floor: SourceTier = SourceTier.OSINT_ANALYSIS,
    ) -> TaggedClaim:
        claim = TaggedClaim(text=text, citations=citations, tier_floor=tier_floor)
        if self.strict and not citations and tier_floor != SourceTier.MODEL_EXTRAPOLATION:
            raise FidelityViolation(
                "strict mode: claim emitted without citations and tier_floor above MODEL_EXTRAPOLATION"
            )
        return claim
