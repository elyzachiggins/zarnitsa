"""Anthropic Claude backbone — cloud default."""

from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

from zarnitsa.config import settings
from zarnitsa.exceptions import ProviderError
from zarnitsa.providers.base import (
    BaseProvider,
    ProviderMessage,
    ProviderResponse,
    SystemPrompt,
    as_blocks,
)

log = logging.getLogger(__name__)

# Anthropic accepts at most 4 cache breakpoints per request.
_MAX_CACHE_BREAKPOINTS = 4


class AnthropicProvider(BaseProvider):
    name = "anthropic"
    is_local = False

    def __init__(self, *, model: str | None = None, api_key: str | None = None) -> None:
        if not (api_key or settings.anthropic_api_key):
            raise ProviderError("ANTHROPIC_API_KEY is not set")
        self.client = AsyncAnthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = model or settings.anthropic_model

    def _system_param(self, system: SystemPrompt | None) -> list[dict[str, object]]:
        """Render a SystemPrompt as Anthropic system blocks with cache breakpoints.

        A breakpoint caches everything from the start of the prompt through the marked
        block, so the caller's block order determines what is reusable. Zarnitsa marks
        two: the shared cultural prior (identical for all five personas) and the
        persona prompt (identical for that persona across every deliberation).
        """
        blocks = as_blocks(system)
        if not blocks:
            return []
        cache_on = settings.prompt_cache
        budget = _MAX_CACHE_BREAKPOINTS
        rendered: list[dict[str, object]] = []
        for block in blocks:
            entry: dict[str, object] = {"type": "text", "text": block.text}
            if cache_on and block.cache and budget > 0:
                entry["cache_control"] = {"type": "ephemeral"}
                budget -= 1
            rendered.append(entry)
        return rendered

    async def complete(
        self,
        messages: list[ProviderMessage],
        *,
        system: SystemPrompt | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        # `temperature` is accepted for interface compatibility but deliberately not
        # forwarded: it was removed in the Opus 4.7 generation and sending it returns
        # a 400. Callers that need output variation should steer via the prompt.
        formatted = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=self._system_param(system),
                messages=formatted,
            )
        except Exception as e:  # narrow this when we wire structured errors
            raise ProviderError(f"Anthropic call failed: {e}") from e

        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        usage = resp.usage
        return ProviderResponse(
            content=text,
            model=self.model,
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            stop_reason=resp.stop_reason,
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0 if usage else 0,
            cache_write_tokens=(
                getattr(usage, "cache_creation_input_tokens", 0) or 0 if usage else 0
            ),
        )

    async def aclose(self) -> None:
        await self.client.close()
