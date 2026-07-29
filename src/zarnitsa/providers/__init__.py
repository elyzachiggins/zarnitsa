"""Backbone providers — cloud (Anthropic / Gemini / OpenRouter) and offline (Ollama)."""

from zarnitsa.providers.base import (
    BaseProvider,
    ProviderMessage,
    ProviderResponse,
    SystemBlock,
    SystemPrompt,
    flatten_system,
)
from zarnitsa.providers.factory import get_provider, get_provider_for

__all__ = [
    "BaseProvider",
    "ProviderMessage",
    "ProviderResponse",
    "SystemBlock",
    "SystemPrompt",
    "flatten_system",
    "get_provider",
    "get_provider_for",
]
