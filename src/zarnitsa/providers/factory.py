"""Resolve a provider instance from settings or an override."""

from __future__ import annotations

from functools import lru_cache

from zarnitsa.config import Backbone, settings
from zarnitsa.exceptions import ProviderError
from zarnitsa.providers.base import BaseProvider
from zarnitsa.types import PersonaRole


@lru_cache(maxsize=8)
def get_provider(
    backbone: Backbone | None = None,
    model: str | None = None,
) -> BaseProvider:
    """Return a cached provider bound to (backbone, model).

    Cached on both arguments so a council that routes CINC to a different model than
    the supporting personas reuses two long-lived clients rather than rebuilding one
    per call.
    """
    chosen: Backbone = backbone or settings.backbone

    if chosen == "anthropic":
        from zarnitsa.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider(model=model)
    if chosen == "openrouter":
        from zarnitsa.providers.openrouter_provider import OpenRouterProvider

        return OpenRouterProvider(model=model)
    if chosen == "ollama":
        from zarnitsa.providers.ollama_provider import OllamaProvider

        return OllamaProvider(model=model)
    raise ProviderError(f"Provider '{chosen}' is not yet implemented")


def get_provider_for(role: PersonaRole) -> BaseProvider:
    """Return the provider configured for a given council seat.

    CINC writes the synthesis that is surfaced to the user, so it can be routed to a
    stronger model than the four supporting personas whose output is consumed mainly
    by CINC itself. With both unset this collapses to a single shared provider.
    """
    backbone, model = settings.backbone_for(is_cinc=role == PersonaRole.CINC)
    return get_provider(backbone, model)
