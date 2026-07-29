"""Domain exceptions for Zarnitsa."""


class ZarnitsaError(Exception):
    """Base error class."""


class ProviderError(ZarnitsaError):
    """Backbone provider failed (network, auth, rate limit, etc.)."""


class CorpusError(ZarnitsaError):
    """Corpus loader or retrieval failed."""


class PersonaError(ZarnitsaError):
    """Persona definition is missing or malformed."""


class FidelityViolation(ZarnitsaError):
    """A claim was emitted without corpus support under strict fidelity mode."""


class CorpusUnavailable(CorpusError):
    """The corpus could not be loaded, so no grounded analysis is possible.

    Distinct from CorpusError so the API can map it to 503 (a real, temporary,
    operator-fixable outage) rather than a generic 500. Raised instead of silently
    degrading, because output that looks corpus-grounded but isn't is worse than no
    output at all for this use case.
    """
