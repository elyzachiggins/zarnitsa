"""Pydantic schemas for the API surface.

The `/v1/chat/completions` endpoint mirrors the OpenAI shape so any OpenAI-compatible
client (Open-WebUI, LibreChat, the OpenAI Python SDK pointed at a custom base_url)
can call Zarnitsa without code changes.
"""

from __future__ import annotations

import time
import uuid

from pydantic import BaseModel, Field


class OAIMessage(BaseModel):
    role: str
    content: str


class OAIChatCompletionRequest(BaseModel):
    model: str = "zarnitsa-cgs"
    messages: list[OAIMessage]
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False
    # Zarnitsa extension — pick a persona by role string
    persona: str | None = None


class OAIChoice(BaseModel):
    index: int = 0
    message: OAIMessage
    finish_reason: str | None = "stop"


class OAIUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class OAIChatCompletionResponse(BaseModel):
    id: str = Field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:24]}")
    object: str = "chat.completion"
    created: int = Field(default_factory=lambda: int(time.time()))
    model: str
    choices: list[OAIChoice]
    usage: OAIUsage = Field(default_factory=OAIUsage)
