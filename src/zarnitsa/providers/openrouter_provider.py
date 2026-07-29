"""OpenRouter backbone — one key, many models.

OpenRouter speaks the OpenAI chat-completions shape, so the system prompt collapses
to a single leading `system` message. There is no cross-request prompt caching to opt
into here: some upstream providers cache automatically, but it is not controllable
from the client, so `SystemBlock.cache` flags are ignored.

Why this provider exists: Zarnitsa runs five model calls per deliberation with 6–8k
max_tokens each, which makes it output-price dominated. Routing the four supporting
personas to a cheap long-context model and keeping only CINC on a premium one cuts
cost by an order of magnitude without touching the synthesis the user reads.
"""

from __future__ import annotations

import httpx

from zarnitsa.config import settings
from zarnitsa.exceptions import ProviderError
from zarnitsa.providers.base import (
    BaseProvider,
    ProviderMessage,
    ProviderResponse,
    SystemPrompt,
    flatten_system,
)

_TIMEOUT = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)


class OpenRouterProvider(BaseProvider):
    name = "openrouter"
    is_local = False

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        key = api_key or settings.openrouter_api_key
        if not key:
            raise ProviderError("OPENROUTER_API_KEY is not set")
        self.model = model or settings.openrouter_model
        self.client = httpx.AsyncClient(
            base_url=base_url or settings.openrouter_base_url,
            timeout=_TIMEOUT,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                # OpenRouter attribution headers — optional, used for their rankings.
                "HTTP-Referer": settings.openrouter_referer,
                "X-Title": settings.openrouter_title,
            },
        )

    async def complete(
        self,
        messages: list[ProviderMessage],
        *,
        system: SystemPrompt | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        payload_messages: list[dict[str, str]] = []
        system_text = flatten_system(system)
        if system_text:
            payload_messages.append({"role": "system", "content": system_text})
        payload_messages.extend(
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant", "system")
        )

        body: dict[str, object] = {
            "model": self.model,
            "messages": payload_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
            # Ask OpenRouter to include its own accounting in the response so the
            # eval harness can report real spend instead of estimating from a table.
            "usage": {"include": True},
        }

        try:
            resp = await self.client.post("/chat/completions", json=body)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            detail = e.response.text[:400] if e.response is not None else ""
            raise ProviderError(
                f"OpenRouter call failed ({e.response.status_code}): {detail}"
            ) from e
        except httpx.HTTPError as e:
            raise ProviderError(f"OpenRouter call failed: {e}") from e

        data = resp.json()

        # OpenRouter returns upstream failures as a 200 with an `error` object.
        if isinstance(data.get("error"), dict):
            err = data["error"]
            raise ProviderError(
                f"OpenRouter upstream error {err.get('code', '?')}: {err.get('message', '')}"
            )

        choices = data.get("choices") or []
        if not choices:
            raise ProviderError(f"OpenRouter returned no choices: {str(data)[:300]}")

        choice = choices[0]
        content = (choice.get("message") or {}).get("content") or ""
        usage = data.get("usage") or {}
        cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0

        return ProviderResponse(
            content=content,
            model=data.get("model") or self.model,
            input_tokens=usage.get("prompt_tokens", 0) or 0,
            output_tokens=usage.get("completion_tokens", 0) or 0,
            stop_reason=choice.get("finish_reason"),
            cache_read_tokens=cached,
            cost_usd=usage.get("cost"),
        )

    async def aclose(self) -> None:
        await self.client.aclose()
