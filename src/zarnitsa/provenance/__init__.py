"""Provenance engine — tags every claim with its source tier."""

from zarnitsa.provenance.extract import citation_coverage, extract_citations
from zarnitsa.provenance.tagger import ProvenanceTagger, TaggedClaim

__all__ = [
    "ProvenanceTagger",
    "TaggedClaim",
    "citation_coverage",
    "extract_citations",
]
