"""Council deliberation DAG.

Staged parallel execution:
    Stage 1: GRU       (intel brief — all subsequent stages see this)
    Stage 2: MOD, CGS  (parallel: war-economy/procurement + operational planning)
    Stage 3: SOVBEZ    (political-security synthesis — sees Stages 1+2)
    Stage 4: CINC      (strategic vector, red lines, authorization — sees everything)
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from zarnitsa.config import settings
from zarnitsa.corpus.entry import CorpusEntry
from zarnitsa.corpus.retrieval import Retriever
from zarnitsa.exceptions import CorpusUnavailable
from zarnitsa.orchestrator.cultural_prior import CULTURAL_PRIOR
from zarnitsa.orchestrator.grounding import Grounding, GroundingStatus
from zarnitsa.personas import load_personas
from zarnitsa.personas.loader import Persona
from zarnitsa.provenance.extract import extract_citations
from zarnitsa.provenance.verify import summarise, verify_turn
from zarnitsa.providers import ProviderMessage, SystemBlock, get_provider_for
from zarnitsa.types import CouncilRequest, CouncilResponse, PersonaRole, PersonaTurn, WargameMode

if TYPE_CHECKING:
    from zarnitsa.providers.base import BaseProvider

log = logging.getLogger(__name__)

# Module-level singleton — corpus loads and indexes once on first request.
_retriever: Retriever | None = None

RetrievalResults = list[tuple[CorpusEntry, float]]


def _get_retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever()
        log.info("Corpus retriever initialised: %d entries indexed", len(_retriever))
    return _retriever


def _retrieve(request: CouncilRequest) -> tuple[RetrievalResults, Grounding]:
    """Retrieve grounding entries once per deliberation, reporting grounding status.

    Retrieval is hoisted here because it depends only on the scenario; each persona
    used to run it independently with the identical query, scanning the corpus five
    times for five identical result sets.

    This deliberately does NOT swallow a corpus failure. The previous version returned
    an empty list and logged, which is how a broken corpus stayed invisible through
    weeks of ungrounded deliberations. The failure is now a value the caller must
    handle.
    """
    try:
        retriever = _get_retriever()
    except Exception as e:
        log.exception("Corpus failed to load")
        return [], Grounding(
            status=GroundingStatus.CORPUS_UNAVAILABLE,
            detail=str(e),
        )

    corpus_errors = [str(err) for err in retriever.errors]
    try:
        results = retriever.search(request.scenario, top_k=settings.retrieval_top_k)
    except Exception as e:
        log.exception("Corpus retrieval failed")
        return [], Grounding(
            status=GroundingStatus.CORPUS_UNAVAILABLE,
            corpus_size=len(retriever),
            corpus_errors=corpus_errors,
            detail=str(e),
        )

    if not results:
        status = GroundingStatus.NO_MATCH
    elif corpus_errors:
        status = GroundingStatus.DEGRADED
    else:
        status = GroundingStatus.GROUNDED

    return results, Grounding(
        status=status,
        entry_ids=[e.id for e, _ in results],
        corpus_size=len(retriever),
        corpus_errors=corpus_errors,
    )


def _format_corpus_context(results: RetrievalResults) -> str:
    if not results:
        return ""
    blocks = []
    for entry, _score in results:
        snippet = entry.content[:700].rstrip()
        if len(entry.content) > 700:
            snippet += "…"
        blocks.append(
            f"[{entry.tier.value.upper()} | {entry.id}]\n"
            f"**{entry.title}**\n\n"
            f"{snippet}"
        )
    return (
        "# Corpus — retrieved grounding material\n\n"
        "The following entries are drawn from the verified doctrine and source corpus. "
        "Ground your analysis in this material where relevant. "
        "When you draw on an entry, cite it inline using its exact entry_id as shown in "
        "the bracketed header (for example: [primary_doctrine | military_doctrine_2014]). "
        "Citations are extracted by exact id match — an id you invent will be discarded, "
        "so cite only ids that appear above.\n\n"
        + "\n\n---\n\n".join(blocks)
    )


STAGE_1 = [PersonaRole.GRU]
STAGE_2 = [PersonaRole.MOD, PersonaRole.CGS]
STAGE_3 = [PersonaRole.SOVBEZ]
STAGE_4 = [PersonaRole.CINC]

STAGES = [STAGE_1, STAGE_2, STAGE_3, STAGE_4]


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

# The language rules and cultural prior are byte-identical for all five personas and
# across every deliberation, so they form the shared cache prefix. The persona prompt
# is stable per seat, so it gets its own breakpoint: seat N's second block is reused
# across requests while the first block is reused across seats within a request.
_SHARED_PREFIX = f"{_LANGUAGE_INSTRUCTION}\n\n---\n\n{CULTURAL_PRIOR}"


def _compose_system_prompt(persona_system: str) -> list[SystemBlock]:
    return [
        SystemBlock(text=_SHARED_PREFIX, cache=True),
        SystemBlock(text=persona_system, cache=True),
    ]


def _format_priors(turns: list[PersonaTurn]) -> str:
    if not turns:
        return ""
    blocks = [f"## Prior council input — {t.persona.value}\n\n{t.content}" for t in turns]
    return "\n\n".join(blocks)


_MODE_HEADERS: dict[WargameMode, str] = {
    # STRATEGIC is the default mode on CouncilRequest. It previously had no entry
    # here, so the default path shipped no output-structure guidance at all.
    WargameMode.STRATEGIC: (
        "# Mode — STRATEGIC (advisory)\n"
        "Standing advisory deliberation, not a scored wargame turn. Your output must: "
        "(1) give your ASSESSMENT of the situation from your institutional position; "
        "(2) state the IMPLICATIONS for Russian strategic interests; "
        "(3) cite DOCTRINAL BASIS; "
        "(4) identify RISKS and uncertainties, marking fidelity where the corpus is thin; "
        "(5) state what you RECOMMEND to the council."
    ),
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
_MAX_TOKENS_CINC = 8192  # CINC sees all prior turns + corpus; needs headroom for synthesis


def _build_user_message(
    persona: Persona,
    request: CouncilRequest,
    priors: list[PersonaTurn],
    corpus_context: str,
) -> str:
    parts: list[str] = []
    if request.prior_exchanges:
        history = "\n\n".join(
            f"[Prior exchange {i + 1}]\nScenario: {ex.get('scenario', '')}\n"
            f"Summary: {ex.get('summary', '')}"
            for i, ex in enumerate(request.prior_exchanges[-3:])
        )
        parts.append(f"# Session history (for context)\n\n{history}")
    parts.append(f"# Scenario\n\n{request.scenario}")
    if request.cinc_intent:
        parts.append(f"# CinC stated intent\n\n{request.cinc_intent}")
    if request.constraints:
        parts.append("# Constraints\n\n" + "\n".join(f"- {c}" for c in request.constraints))
    if corpus_context:
        parts.append(corpus_context)
    priors_text = _format_priors(priors)
    if priors_text:
        parts.append(priors_text)
    mode_instruction = _mode_instruction(request.wargame_mode, persona.role)
    if mode_instruction:
        parts.append(mode_instruction)
    parts.append(
        f"# Your turn\n\nSpeak now as {persona.title} ({persona.russian_name}). "
        "Follow your defined output format. Be specific. Mark fidelity."
    )
    return "\n\n".join(parts)


async def _run_persona(
    prov: BaseProvider,
    persona: Persona,
    request: CouncilRequest,
    priors: list[PersonaTurn],
    retrieved: RetrievalResults,
    corpus_context: str,
    max_tokens: int = _MAX_TOKENS_DEFAULT,
) -> PersonaTurn:
    user_msg = _build_user_message(persona, request, priors, corpus_context)

    resp = await prov.complete(
        messages=[ProviderMessage(role="user", content=user_msg)],
        system=_compose_system_prompt(persona.system_prompt),
        max_tokens=max_tokens,
    )

    return PersonaTurn(
        persona=persona.role,
        content=resp.content,
        citations=extract_citations(resp.content, retrieved),
        usage={
            "model": resp.model,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "cache_read_tokens": resp.cache_read_tokens,
            "cache_write_tokens": resp.cache_write_tokens,
            "cost_usd": resp.cost_usd,
            "stop_reason": resp.stop_reason,
        },
    )


async def _run_stage(
    roles: list[PersonaRole],
    personas: dict[PersonaRole, Persona],
    request: CouncilRequest,
    priors: list[PersonaTurn],
    retrieved: RetrievalResults,
    corpus_context: str,
    provider: BaseProvider | None,
) -> list[PersonaTurn]:
    tasks = [
        _run_persona(
            provider or get_provider_for(role),
            personas[role],
            request,
            priors,
            retrieved,
            corpus_context,
            max_tokens=_MAX_TOKENS_CINC if role == PersonaRole.CINC else _MAX_TOKENS_DEFAULT,
        )
        for role in roles
        if role in personas
    ]
    results = await asyncio.gather(*tasks)
    return list(results)


def _aggregate_usage(turns: list[PersonaTurn]) -> dict[str, Any]:
    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    cost = 0.0
    cost_reported = False
    models: list[str] = []
    for turn in turns:
        usage = turn.usage or {}
        for key in totals:
            totals[key] += int(usage.get(key) or 0)
        if usage.get("cost_usd") is not None:
            cost += float(usage["cost_usd"])
            cost_reported = True
        model = usage.get("model")
        if model and model not in models:
            models.append(model)
    return {
        **totals,
        "cost_usd": round(cost, 6) if cost_reported else None,
        "models": models,
    }


def _check_grounding(grounding: Grounding) -> None:
    """Refuse to produce ungrounded analysis when the corpus is broken.

    NO_MATCH is not an error — an obscure scenario legitimately retrieves nothing, and
    the council can still reason from its institutional priors. CORPUS_UNAVAILABLE is
    different: it means the grounding machinery is broken, and returning output that
    looks corpus-supported but isn't is the exact failure this whole change exists to
    prevent. Set ZARNITSA_REQUIRE_GROUNDING=false to allow it anyway.
    """
    if (
        settings.require_grounding
        and grounding.status is GroundingStatus.CORPUS_UNAVAILABLE
    ):
        raise CorpusUnavailable(
            f"corpus unavailable, refusing to produce ungrounded analysis: "
            f"{grounding.detail}"
        )


async def run_council_streaming(
    request: CouncilRequest,
    *,
    provider: BaseProvider | None = None,
) -> AsyncIterator[Grounding | PersonaTurn]:
    """Yield the Grounding status first, then each PersonaTurn as its stage completes.

    Grounding comes first so a client can render a "no source material" caveat before
    any analysis appears, rather than after the user has already read it.
    """
    personas = {p.role: p for p in load_personas()}
    retrieved, grounding = _retrieve(request)
    _check_grounding(grounding)
    yield grounding

    corpus_context = _format_corpus_context(retrieved)
    all_turns: list[PersonaTurn] = []

    for stage in STAGES:
        stage_turns = await _run_stage(
            stage, personas, request, all_turns, retrieved, corpus_context, provider
        )
        all_turns.extend(stage_turns)
        for turn in stage_turns:
            yield turn


async def run_council(
    request: CouncilRequest,
    *,
    provider: BaseProvider | None = None,
) -> CouncilResponse:
    """Run council deliberation in staged parallel execution.

    Delegates to the LangGraph StateGraph when ZARNITSA_USE_LANGGRAPH is set. Both
    paths call the same per-seat function, so they produce identical output; the graph
    adds checkpointing and node-level streaming at the cost of a large dependency in
    the request path.
    """
    if settings.use_langgraph:
        from zarnitsa.orchestrator.langgraph_council import run_council_graph

        return await run_council_graph(request, provider=provider)

    personas = {p.role: p for p in load_personas()}
    retrieved, grounding = _retrieve(request)
    _check_grounding(grounding)

    corpus_context = _format_corpus_context(retrieved)
    all_turns: list[PersonaTurn] = []

    for stage in STAGES:
        stage_turns = await _run_stage(
            stage, personas, request, all_turns, retrieved, corpus_context, provider
        )
        all_turns.extend(stage_turns)

    return _assemble_response(request, all_turns, grounding, retrieved)


def _assemble_response(
    request: CouncilRequest,
    all_turns: list[PersonaTurn],
    grounding: Grounding,
    retrieved: RetrievalResults | None = None,
) -> CouncilResponse:
    final = next(
        (t.content for t in reversed(all_turns) if t.persona == PersonaRole.CINC),
        all_turns[-1].content if all_turns else "No deliberation.",
    )

    metadata: dict[str, Any] = {
        "wargame_mode": request.wargame_mode.value,
        "personas_engaged": [t.persona.value for t in all_turns],
        "retrieved_entries": grounding.entry_ids,
        "grounding": grounding.to_dict(),
        "usage": _aggregate_usage(all_turns),
    }

    if settings.verify_claims and retrieved:
        checks = [
            check
            for turn in all_turns
            for check in verify_turn(turn.content, turn.citations, retrieved)
        ]
        metadata["verification"] = summarise(checks).to_dict()

    return CouncilResponse(
        recommendation=final,
        courses_of_action=[],
        dissents=[],
        turns=all_turns,
        knowledge_horizon=None,
        metadata=metadata,
    )


def build_council_graph() -> Any:
    """Compile the LangGraph StateGraph for the council DAG.

    Re-exported from langgraph_council so the historical import path keeps working.
    Imported lazily because langgraph is an optional dependency — the default
    execution path does not need it.
    """
    from zarnitsa.orchestrator.langgraph_council import build_council_graph as _build

    return _build()
