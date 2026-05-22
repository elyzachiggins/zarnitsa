"""Resolve a provider instance from settings or an override."""

from __future__ import annotations

from functools import lru_cache

from zarnitsa.config import Backbone, settings
from zarnitsa.exceptions import ProviderError
from zarnitsa.providers.base import BaseProvider


@lru_cache(maxsize=4)
def get_provider(backbone: Backbone | None = None) -> BaseProvider:
    chosen: Backbone = backbone or settings.backbone

    if chosen == "anthropic":
        from zarnitsa.providers.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if chosen == "ollama":
        from zarnitsa.providers.ollama_provider import OllamaProvider

        return OllamaProvider()
    raise ProviderError(f"Provider '{chosen}' is not yet implemented")
