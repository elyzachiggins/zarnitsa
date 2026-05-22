"""Runtime settings loaded from environment / .env."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Backbone = Literal["anthropic", "gemini", "openrouter", "ollama"]
FidelityMode = Literal["strict", "permissive"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ZARNITSA_",
        extra="ignore",
    )

    backbone: Backbone = "anthropic"

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")

    anthropic_model: str = "claude-opus-4-7"
    gemini_model: str = "gemini-2.5-pro"
    ollama_model: str = "gemma3:27b"
    ollama_host: str = "http://localhost:11434"

    corpus_snapshot: str = "2026-05"
    data_dir: Path = Path("data")

    host: str = "127.0.0.1"
    port: int = 8000

    fidelity_mode: FidelityMode = "strict"


settings = Settings()  # type: ignore[call-arg]
