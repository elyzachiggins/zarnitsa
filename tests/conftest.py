"""Shared fixtures.

The council path is exercised against a recording fake provider rather than a live
backbone, so the full four-stage DAG — staging order, prior-turn threading, cache
block layout, citation extraction — is covered by tests that cost nothing to run.
"""

from __future__ import annotations

import pytest

from zarnitsa.providers.base import (
    BaseProvider,
    ProviderMessage,
    ProviderResponse,
    SystemPrompt,
    as_blocks,
)


class FakeProvider(BaseProvider):
    """Records every call and returns a scripted reply."""

    name = "fake"
    is_local = True

    def __init__(self, reply: str = "Comrades. Assessment follows.") -> None:
        self.reply = reply
        self.model = "fake-model"
        self.calls: list[dict[str, object]] = []

    async def complete(
        self,
        messages: list[ProviderMessage],
        *,
        system: SystemPrompt | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> ProviderResponse:
        blocks = as_blocks(system)
        self.calls.append(
            {
                "user": messages[-1].content if messages else "",
                "system_blocks": blocks,
                "system_text": "\n\n".join(b.text for b in blocks),
                "max_tokens": max_tokens,
            }
        )
        return ProviderResponse(
            content=self.reply,
            model=self.model,
            input_tokens=100,
            output_tokens=50,
            stop_reason="end_turn",
        )


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()
