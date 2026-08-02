"""Council deliberation DAG.

Sequential execution — each stage sees the full output of all prior stages:
    Stage 1: CGS     (intelligence + operational assessment; НГШ, absorbs GRU intel)
    Stage 2: MOD     (war-economy / procurement / political-military; sees CGS)
    Stage 3: SOVBEZ  (political-security synthesis; sees CGS + MOD)
    Stage 4: CINC    (strategic vector, red lines, authorization; sees everything)
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from zarnitsa.corpus.chunker import Chunk
from zarnitsa.corpus.index import ChunkIndex
from zarnitsa.orchestrator.cultural_prior import CULTURAL_PRIOR
from zarnitsa.personas import load_personas
from zarnitsa.personas.loader import Persona
from zarnitsa.providers import ProviderMessage, get_provider
from zarnitsa.types import (
    Citation,
    CouncilRequest,
    CouncilResponse,
    PersonaRole,
    PersonaTurn,
    WargameMode,
)

if TYPE_CHECKING:
    from zarnitsa.providers.base import BaseProvider

log = logging.getLogger(__name__)

# Module-level singleton — vector index loads once, lazily.
_index: ChunkIndex | None = None
_index_loaded = False

_RETRIEVAL_TOP_K = 6


def _get_index() -> ChunkIndex | None:
    """Load the precomputed chunk index once; degrade gracefully if absent."""
    global _index, _index_loaded
    if not _index_loaded:
        _index_loaded = True
        try:
            _index = ChunkIndex.load()
            log.info("Vector index loaded: %d chunks", len(_index.chunks))
        except Exception as e:  # noqa: BLE001 — run ungrounded if index/token missing
            log.warning("Vector index unavailable (%s) — deliberation runs ungrounded until built", e)
            _index = None
    return _index


def _format_chunk_context(chunks: list[Chunk]) -> str:
    """Grounding block. Deliberately instructs against inline citations —
    provenance is carried in PersonaTurn.citations and shown only on request."""
    blocks = []
    for c in chunks:
        label = c.title + (f" — {c.anchor}" if c.anchor else "")
        blocks.append(f"[{c.tier.value}] {label}\n{c.text}")
    return (
        "# Grounding material (retrieved from the verified corpus)\n\n"
        "Base your analysis on the material below where relevant. Write clean analytical prose. "
        "Do NOT insert citations, source tags, entry ids, or URLs into your output — provenance is "
        "tracked separately and surfaced only on request.\n\n"
        + "\n\n---\n\n".join(blocks)
    )


def _chunk_snippet(c: Chunk) -> str:
    head = " ".join(c.text.split())[:160]
    return f"{c.anchor}: {head}" if c.anchor else head

STAGE_1 = [PersonaRole.CGS]
STAGE_2 = [PersonaRole.MOD]
STAGE_3 = [PersonaRole.SOVBEZ]
STAGE_4 = [PersonaRole.CINC]


_LANGUAGE_INSTRUCTION = (
    "LANGUAGE: All text must be written in English first. "
    "Russian is permitted only as a parenthetical gloss immediately after the English, never as standalone text. "
    "Correct: '## Situation Assessment (Оценка обстановки)' or 'regrouping (перегруппировка)'. "
    "Incorrect: '## Оценка обстановки' or any header, title, or sentence written in Russian without English preceding it. "
    "Opening salutations must be in English: 'Comrades.' not 'Товарищи.' "
    "ABBREVIATIONS: All organizational and institutional abbreviations must be written in Latin transliteration, not Cyrillic. "
    "Use: GRU (not ГРУ), MO (not МО), NGSh (not НГШ), VGK (not ВГК), Sovbez (not Совбез), "
    "GSh (not ГШ), GOU (not ГОУ), GOMU (not ГОМУ), NTsUO (not НЦУО), TsVSI (not ЦВСИ), "
    "REB (not РЭБ), VKS (not ВКС), VMF (not ВМФ), VDV (not ВДВ), MVD (not МВД), "
    "FSB (not ФСБ), SVR (not СВР), FSO (not ФСО), OGV (not ОГВ), OPK (not ОПК), "
    "Rosgvardiya (not Росгвардия), DNR (not ДНР), LNR (not ЛНР). "
    "Doctrinal terms with no English equivalent remain as Russian in parentheses after the English: "
    "'reflexive control (рефлексивное управление)', 'maskirovka (маскировка)', "
    "'operational art (оперативное искусство)', 'correlation of forces and means (соотношение сил и средств)'."
)


def _compose_system_prompt(persona_system: str) -> str:
    return f"{_LANGUAGE_INSTRUCTION}\n\n---\n\n{CULTURAL_PRIOR}\n\n---\n\n{persona_system}"


def _format_priors(turns: list[PersonaTurn]) -> str:
    if not turns:
        return ""
    blocks = [f"## Prior council input — {t.persona.value}\n\n{t.content}" for t in turns]
    return "\n\n".join(blocks)


_MODE_HEADERS: dict[WargameMode, str] = {
    WargameMode.FREEPLAY: (
        "# Wargame mode — MODE 1 (FREEPLAY)\n"
        "The council is determining its own course of action from the scenario. "
        "State your analysis clearly. The final council output must: "
        "(1) STATE the DECISION concisely; "
        "(2) provide RATIONALE for Russian strategic interests; "
        "(3) cite DOCTRINAL BASIS; "
        "(4) identify RISKS and why they are accepted; "
        "(5) state INFORMATION needs for the next decision cycle."
    ),
    WargameMode.PREDETERMINED: (
        "# Wargame mode — MODE 2 (PREDETERMINED ACTIONS)\n"
        "An action has been assigned to Russia. The council's role is to adjudicate it. "
        "Each voice must: "
        "(1) ACKNOWLEDGE the assigned action; "
        "(2) explain RATIONALE — consistency with or divergence from doctrine; "
        "(3) describe EXECUTION with operational detail; "
        "(4) identify FOLLOW-ON actions; "
        "(5) flag UNREALISTIC aspects while still executing."
    ),
    WargameMode.ANALYTIC: (
        "# Wargame mode — ANALYTIC\n"
        "Provide commentary from the Russian institutional perspective. "
        "Your output must: "
        "(1) explain HOW Russia perceives this situation; "
        "(2) identify the RANGE OF OPTIONS consistent with doctrine; "
        "(3) highlight incorrect WESTERN ASSUMPTIONS about Russian behavior; "
        "(4) offer INSIGHTS participants may not have considered."
    ),
}


def _mode_instruction(mode: WargameMode, _role: PersonaRole) -> str:
    return _MODE_HEADERS.get(mode, "")


_MAX_TOKENS_DEFAULT = 6144
_MAX_TOKENS_CINC = 8192  # CINC sees all prior turns + corpus; needs headroom for full synthesis


async def _run_persona(
    prov: BaseProvider,
    persona: Persona,
    request: CouncilRequest,
    priors: list[PersonaTurn],
    max_tokens: int = _MAX_TOKENS_DEFAULT,
) -> PersonaTurn:
    priors_text = _format_priors(priors)
    user_msg_parts = []
    if request.prior_exchanges:
        history = "\n\n".join(
            f"[Prior exchange {i+1}]\nScenario: {ex.get('scenario','')}\nSummary: {ex.get('summary','')}"
            for i, ex in enumerate(request.prior_exchanges[-3:])
        )
        user_msg_parts.append(f"# Session history (for context)\n\n{history}")
    user_msg_parts.append(f"# Scenario\n\n{request.scenario}")
    if request.cinc_intent:
        user_msg_parts.append(f"# CinC stated intent\n\n{request.cinc_intent}")
    if request.constraints:
        user_msg_parts.append("# Constraints\n\n" + "\n".join(f"- {c}" for c in request.constraints))

    citations: list[Citation] = []
    try:
        index = _get_index()
        if index is not None:
            hits = index.search(request.scenario, top_k=_RETRIEVAL_TOP_K, persona=persona.role.value)
            if hits:
                user_msg_parts.append(_format_chunk_context([c for c, _ in hits]))
                citations = [
                    Citation(entry_id=c.entry_id, tier=c.tier, snippet=_chunk_snippet(c))
                    for c, _ in hits
                ]
    except Exception:
        log.exception("Corpus retrieval failed for persona %s — proceeding without grounding", persona.role)

    if priors_text:
        user_msg_parts.append(priors_text)
    mode_instruction = _mode_instruction(request.wargame_mode, persona.role)
    if mode_instruction:
        user_msg_parts.append(mode_instruction)
    user_msg_parts.append(
        f"# Your turn\n\nSpeak now as {persona.title} ({persona.russian_name}). "
        "Follow your defined output format. Be specific. Ground your claims in the retrieved "
        "material; if the corpus does not support a point, say so rather than inventing it. "
        "Write clean prose — do not insert citations, source tags, or entry ids into your output."
    )

    resp = await prov.complete(
        messages=[ProviderMessage(role="user", content="\n\n".join(user_msg_parts))],
        system=_compose_system_prompt(persona.system_prompt),
        max_tokens=max_tokens,
    )
    return PersonaTurn(persona=persona.role, content=resp.content, citations=citations)


async def _run_stage(
    prov: BaseProvider,
    roles: list[PersonaRole],
    personas: dict[PersonaRole, Persona],
    request: CouncilRequest,
    priors: list[PersonaTurn],
) -> list[PersonaTurn]:
    tasks = [
        _run_persona(
            prov, personas[role], request, priors,
            max_tokens=_MAX_TOKENS_CINC if role == PersonaRole.CINC else _MAX_TOKENS_DEFAULT,
        )
        for role in roles
        if role in personas
    ]
    results = await asyncio.gather(*tasks)
    return list(results)


async def run_council_streaming(
    request: CouncilRequest,
    *,
    provider: BaseProvider | None = None,
):
    """Yield PersonaTurn objects as each deliberation stage completes."""
    prov = provider or get_provider()
    personas = {p.role: p for p in load_personas()}
    all_turns: list[PersonaTurn] = []

    for stage in [STAGE_1, STAGE_2, STAGE_3, STAGE_4]:
        stage_turns = await _run_stage(prov, stage, personas, request, all_turns)
        all_turns.extend(stage_turns)
        for turn in stage_turns:
            yield turn


async def run_council(
    request: CouncilRequest,
    *,
    provider: BaseProvider | None = None,
) -> CouncilResponse:
    """Run council deliberation in staged parallel execution."""
    prov = provider or get_provider()
    personas = {p.role: p for p in load_personas()}
    all_turns: list[PersonaTurn] = []

    for stage in [STAGE_1, STAGE_2, STAGE_3, STAGE_4]:
        stage_turns = await _run_stage(prov, stage, personas, request, all_turns)
        all_turns.extend(stage_turns)

    final = next(
        (t.content for t in reversed(all_turns) if t.persona == PersonaRole.CINC),
        all_turns[-1].content if all_turns else "No deliberation.",
    )

    return CouncilResponse(
        recommendation=final,
        courses_of_action=[],
        dissents=[],
        turns=all_turns,
        knowledge_horizon=None,
        metadata={
            "wargame_mode": request.wargame_mode.value,
            "personas_engaged": [t.persona.value for t in all_turns],
        },
    )


def build_council_graph() -> Any:
    raise NotImplementedError("Full LangGraph StateGraph wiring is a future milestone.")
