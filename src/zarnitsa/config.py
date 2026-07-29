"""Runtime settings loaded from environment / .env."""

from __future__ import annotations

from functools import cached_property
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Backbone = Literal["anthropic", "gemini", "openrouter", "ollama"]
FidelityMode = Literal["strict", "permissive"]
RetrievalMode = Literal["bm25", "hybrid"]

# Repo root, derived from this file's location: src/zarnitsa/config.py -> parents[2].
# Only used as a fallback when data_dir can't be resolved against the working directory,
# so an installed (non-editable) package still finds its data.
_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="ZARNITSA_",
        extra="ignore",
    )

    # --- Backbone selection -------------------------------------------------
    # `backbone` drives the four supporting personas (GRU, MOD, CGS, SOVBEZ).
    # CINC produces the synthesis the user actually reads, so it can be routed
    # to a stronger (and more expensive) model independently.
    backbone: Backbone = "anthropic"
    cinc_backbone: Backbone | None = None
    cinc_model: str | None = None

    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")

    anthropic_model: str = "claude-opus-4-7"
    gemini_model: str = "gemini-2.5-pro"
    openrouter_model: str = "deepseek/deepseek-v3.2"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    ollama_model: str = "gemma3:27b"
    ollama_host: str = "http://localhost:11434"

    # Sent by OpenRouter as attribution headers; harmless if unset.
    openrouter_referer: str = "https://github.com/elyzachiggins/zarnitsa"
    openrouter_title: str = "Zarnitsa"

    # --- Corpus / data ------------------------------------------------------
    corpus_snapshot: str = "2026-05"
    data_dir: Path = Path("data")

    # --- Server -------------------------------------------------------------
    host: str = "127.0.0.1"
    port: int = 8000

    # --- Security -----------------------------------------------------------
    # Comma-separated shared secrets accepted on X-API-Key / Authorization: Bearer.
    # EMPTY MEANS THE COUNCIL ENDPOINTS ARE PUBLIC — only safe for local dev.
    api_keys: str = ""
    # Comma-separated CORS origins. "*" is only appropriate when api_keys is set,
    # since a wildcard origin plus no auth means anyone can spend your API budget.
    allowed_origins: str = "*"
    # Council deliberations per identity per window. Each one is 5 model calls.
    rate_limit_requests: int = 20
    rate_limit_window_seconds: int = 3600
    # Redis URL for a shared rate-limit window. Unset = in-process (single worker only).
    redis_url: str = ""

    # --- Behaviour ----------------------------------------------------------
    fidelity_mode: FidelityMode = "strict"
    # Prompt caching on providers that support it. Pure cost optimisation.
    prompt_cache: bool = True
    # Corpus entries retrieved per deliberation.
    retrieval_top_k: int = 6
    # "bm25" (default) or "hybrid" (BM25 + dense, fused by reciprocal rank).
    # Hybrid needs the [offline] extra and is only worth it on a much larger corpus —
    # see src/zarnitsa/corpus/embeddings.py for the reasoning.
    retrieval_mode: RetrievalMode = "bm25"
    embedding_model: str = "intfloat/multilingual-e5-base"
    # Run the lexical claim-support screen on every deliberation. Cheap and
    # deterministic; results land in metadata.verification.
    verify_claims: bool = True
    # Refuse to deliberate when the corpus cannot be loaded, rather than returning
    # analysis that looks corpus-grounded but has no sources behind it. A scenario
    # that simply matches nothing is NOT affected by this — that is a normal result.
    require_grounding: bool = True
    # Route deliberations through the LangGraph StateGraph instead of the hand-rolled
    # asyncio staging. Same output either way; the graph adds checkpointing and
    # node-level streaming, and pulls in a large dependency tree.
    use_langgraph: bool = False

    @cached_property
    def resolved_data_dir(self) -> Path:
        """Absolute path to the data directory.

        Tries, in order: an absolute `data_dir`; `data_dir` relative to the working
        directory; `data_dir` relative to the repo root. The last case is what makes
        a non-editable install work — the previous code hardcoded a parents[3] walk
        in the persona loader that only held for editable installs run from the root.
        """
        if self.data_dir.is_absolute():
            return self.data_dir
        cwd_candidate = Path.cwd() / self.data_dir
        if cwd_candidate.exists():
            return cwd_candidate
        return _REPO_ROOT / self.data_dir

    @property
    def api_key_set(self) -> frozenset[str]:
        return frozenset(k.strip() for k in self.api_keys.split(",") if k.strip())

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def auth_required(self) -> bool:
        return bool(self.api_key_set)

    def backbone_for(self, *, is_cinc: bool) -> tuple[Backbone, str | None]:
        """Return (backbone, model override) for a council seat."""
        if is_cinc:
            return (self.cinc_backbone or self.backbone, self.cinc_model)
        return (self.backbone, None)


settings = Settings()  # type: ignore[call-arg]
