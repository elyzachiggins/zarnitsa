"""Provenance engine — tags every claim with its source tier."""

from zarnitsa.provenance.extract import citation_coverage, extract_citations
from zarnitsa.provenance.tagger import ProvenanceTagger, TaggedClaim
from zarnitsa.provenance.verify import (
    ClaimCheck,
    SupportLevel,
    VerificationSummary,
    summarise,
    verify_turn,
)

__all__ = [
    "ClaimCheck",
    "ProvenanceTagger",
    "SupportLevel",
    "TaggedClaim",
    "VerificationSummary",
    "citation_coverage",
    "extract_citations",
    "summarise",
    "verify_turn",
]
