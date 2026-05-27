"""Anthropic Claude backbone — cloud default."""

from __future__ import annotations

from anthropic import AsyncAnthropic

from zarnitsa.config import settings
from zarnitsa.exceptions import ProviderError
from zarnitsa.providers.base import BaseProvider, ProviderMessage, ProviderResponse


class AnthropicProvider(BaseProvider):
    name = "anthropic"
    is_local = False

    def __init__(self, *, model: str | None = None, api_key: str | None = None) -> None:
        if not (api_key or settings.anthropic_api_key):
            raise ProviderError("ANTHROPIC_API_KEY is not set")
        self.client = AsyncAnthropic(api_key=api_key or settings.anthropic_api_key)
        self.model = model or settings.anthropic_model

    async def complete(
        self,
        messages: list[ProviderMessage],
        *,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        formatted = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        try:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system or "",
                messages=formatted,
            )
        except Exception as e:  # narrow this when we wire structured errors
            raise ProviderError(f"Anthropic call failed: {e}") from e

        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        return ProviderResponse(
            content=text,
            model=self.model,
            input_tokens=resp.usage.input_tokens if resp.usage else 0,
            output_tokens=resp.usage.output_tokens if resp.usage else 0,
            stop_reason=resp.stop_reason,
        )

    async def aclose(self) -> None:
        await self.client.close()
