"""Provider interface — all backbones implement this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProviderMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class ProviderResponse:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None


class BaseProvider(ABC):
    """A pluggable LLM backbone."""

    name: str = "base"
    is_local: bool = False

    @abstractmethod
    async def complete(
        self,
        messages: list[ProviderMessage],
        *,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        """Single completion. Personas call this directly."""

    async def aclose(self) -> None:
        """Release any persistent connections."""
        return None
