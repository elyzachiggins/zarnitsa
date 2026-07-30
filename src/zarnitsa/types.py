"""Core Pydantic models — the wire format for council deliberation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceTier(str, Enum):
    """Provenance tier for a corpus entry or a claim citing one.

    Ordered from highest to lowest authority for adversary-modeling purposes.
    """

    PRIMARY_DOCTRINE = "primary_doctrine"
    KREMLIN_STATEMENT = "kremlin_statement"
    ACADEMIC_RUSSIAN = "academic_russian"
    RUSSIAN_STATE_MEDIA = "russian_state_media"
    RUSSIAN_MILBLOGGER = "russian_milblogger"
    OSINT_ANALYSIS = "osint_analysis"
    MODEL_EXTRAPOLATION = "model_extrapolation"


class PersonaRole(str, Enum):
    """The institutional roles modeled in the council.

    Four-seat sequential council reflecting the Russian decision-making apparatus.
    The General Staff absorbs the intelligence function (the GRU is a directorate
    of the General Staff), so the CGS opens the cycle with the intel + operational
    assessment that all subsequent stages build on:
        Stage 1 — CGS (intelligence + operational assessment; НГШ)
        Stage 2 — MOD (war-economy / procurement / political-military; sees CGS)
        Stage 3 — SOVBEZ (political-security synthesis; sees CGS + MOD)
        Stage 4 — CINC (strategic vector and authorization; sees everything)
    """

    CGS = "chief_of_general_staff"           # НГШ (triple-hatted: CGS + First Deputy MoD + ОГВ commander; absorbs GRU intel)
    MOD = "minister_of_defense"              # МО
    SOVBEZ = "security_council"              # Совбез
    CINC = "commander_in_chief"              # ВГК


class ChatMessage(BaseModel):
    """OpenAI-compatible chat message."""

    role: str
    content: str


class Citation(BaseModel):
    """A reference from a persona output back to a corpus entry."""

    entry_id: str
    tier: SourceTier
    snippet: str = ""
    date: str | None = None


class PersonaTurn(BaseModel):
    """One persona's contribution to a council deliberation."""

    persona: PersonaRole
    content: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float | None = None  # 0.0–1.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WargameMode(str, Enum):
    """Interaction mode for wargame deliberations.

    FREEPLAY: council determines action from the scenario (MODE 1).
    PREDETERMINED: an action is assigned; council adjudicates rationale and execution (MODE 2).
    ANALYTIC: commentary mode — range of options, western assumption gaps, doctrinal analysis.
    STRATEGIC: default non-wargame advisory mode.
    """

    FREEPLAY = "freeplay"
    PREDETERMINED = "predetermined"
    ANALYTIC = "analytic"
    STRATEGIC = "strategic"


class CouncilRequest(BaseModel):
    """Input to a council deliberation."""

    scenario: str
    cinc_intent: str | None = None
    constraints: list[str] = Field(default_factory=list)
    wargame_mode: WargameMode = WargameMode.STRATEGIC
    prior_exchanges: list[dict[str, str]] = Field(default_factory=list)


class CouncilResponse(BaseModel):
    """Output of a council deliberation."""

    recommendation: str
    courses_of_action: list[str] = Field(default_factory=list)
    dissents: list[str] = Field(default_factory=list)
    turns: list[PersonaTurn] = Field(default_factory=list)
    knowledge_horizon: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
