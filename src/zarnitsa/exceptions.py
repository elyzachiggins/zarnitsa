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
