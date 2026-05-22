"""Ollama backbone — offline default (Gemma 4 26B MoE, Qwen 3.5 72B, etc.)."""

from __future__ import annotations

import httpx

from zarnitsa.config import settings
from zarnitsa.exceptions import ProviderError
from zarnitsa.providers.base import BaseProvider, ProviderMessage, ProviderResponse


class OllamaProvider(BaseProvider):
    name = "ollama"
    is_local = True

    def __init__(self, *, model: str | None = None, host: str | None = None) -> None:
        self.model = model or settings.ollama_model
        self.host = host or settings.ollama_host
        self.client = httpx.AsyncClient(base_url=self.host, timeout=120.0)

    async def complete(
        self,
        messages: list[ProviderMessage],
        *,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        payload_messages: list[dict[str, str]] = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        payload_messages.extend({"role": m.role, "content": m.content} for m in messages)

        try:
            resp = await self.client.post(
                "/api/chat",
                json={
                    "model": self.model,
                    "messages": payload_messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    },
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            raise ProviderError(f"Ollama call failed: {e}") from e

        data = resp.json()
        return ProviderResponse(
            content=data.get("message", {}).get("content", ""),
            model=self.model,
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            stop_reason=data.get("done_reason"),
        )

    async def aclose(self) -> None:
        await self.client.aclose()
