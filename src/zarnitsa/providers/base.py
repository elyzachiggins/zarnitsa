"""Provider interface — all backbones implement this."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProviderMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class SystemBlock:
    """One segment of a system prompt.

    `cache=True` marks a cache breakpoint at the end of this block. Providers that
    support prompt caching (Anthropic) translate it into a real breakpoint; providers
    that don't simply concatenate the text and ignore the flag.

    Ordering matters: blocks render in list order, and a breakpoint covers everything
    from the start of the prompt through the marked block. Put stable content first —
    one changed byte anywhere in the prefix invalidates every breakpoint after it.
    """

    text: str
    cache: bool = False


# A system prompt is either a plain string or an ordered list of blocks.
SystemPrompt = str | list[SystemBlock]


def as_blocks(system: SystemPrompt | None) -> list[SystemBlock]:
    """Normalise a SystemPrompt to a list of non-empty blocks."""
    if system is None:
        return []
    if isinstance(system, str):
        return [SystemBlock(text=system)] if system else []
    return [b for b in system if b.text]


def flatten_system(system: SystemPrompt | None) -> str:
    """Collapse a SystemPrompt to plain text, for providers without caching."""
    return "\n\n".join(b.text for b in as_blocks(system))


@dataclass
class ProviderResponse:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None
    # Prompt-caching telemetry. Zero on providers that don't report it.
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    # Provider-reported cost in USD, when available (OpenRouter reports this).
    cost_usd: float | None = None


class BaseProvider(ABC):
    """A pluggable LLM backbone."""

    name: str = "base"
    is_local: bool = False
    model: str = ""

    @abstractmethod
    async def complete(
        self,
        messages: list[ProviderMessage],
        *,
        system: SystemPrompt | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        """Single completion. Personas call this directly."""

    async def aclose(self) -> None:
        """Release any persistent connections."""
        return None


__all__ = [
    "BaseProvider",
    "ProviderMessage",
    "ProviderResponse",
    "SystemBlock",
    "SystemPrompt",
    "as_blocks",
    "flatten_system",
]
