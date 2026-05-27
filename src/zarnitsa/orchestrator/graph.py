"""Council deliberation DAG.

Staged parallel execution:
    Stage 1: GRU  (intel assessment — all subsequent stages see this)
    Stage 2: GOU, GOMU, VBpS, TsVSI, Econ  (parallel specialist tier)
    Stage 3: CGS  (synthesis — sees all of stage 1+2)
    Stage 4: Sino liaison, MoD  (parallel political-military review)
    Stage 5: CinC  (strategic vector, red lines, authorization — sees everything)
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from zarnitsa.orchestrator.cultural_prior import CULTURAL_PRIOR
from zarnitsa.personas import load_personas
from zarnitsa.personas.loader import Persona
from zarnitsa.providers import ProviderMessage, get_provider
from zarnitsa.types import CouncilRequest, CouncilResponse, PersonaRole, PersonaTurn, WargameMode

if TYPE_CHECKING:
    from zarnitsa.providers.base import BaseProvider

STAGE_1 = [PersonaRole.GRU]
STAGE_2 = [PersonaRole.GOU, PersonaRole.GOMU, PersonaRole.VBPS, PersonaRole.TSVSI, PersonaRole.ECON_ADVISOR]
STAGE_3 = [PersonaRole.CGS]
STAGE_4 = [PersonaRole.SINO_LIAISON, PersonaRole.MOD]
STAGE_5 = [PersonaRole.CINC]


def _compose_system_prompt(persona_system: str) -> str:
    return f"{CULTURAL_PRIOR}\n\n---\n\n{persona_system}"


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


async def _run_persona(
    prov: BaseProvider,
    persona: Persona,
    request: CouncilRequest,
    priors: list[PersonaTurn],
) -> PersonaTurn:
    priors_text = _format_priors(priors)
    user_msg_parts = [f"# Scenario\n\n{request.scenario}"]
    if request.cinc_intent:
        user_msg_parts.append(f"# CinC stated intent\n\n{request.cinc_intent}")
    if request.constraints:
        user_msg_parts.append("# Constraints\n\n" + "\n".join(f"- {c}" for c in request.constraints))
    if priors_text:
        user_msg_parts.append(priors_text)
    mode_instruction = _mode_instruction(request.wargame_mode, persona.role)
    if mode_instruction:
        user_msg_parts.append(mode_instruction)
    user_msg_parts.append(
        f"# Your turn\n\nSpeak now as {persona.title} ({persona.russian_name}). "
        "Follow your defined output format. Be specific. Mark fidelity."
    )

    resp = await prov.complete(
        messages=[ProviderMessage(role="user", content="\n\n".join(user_msg_parts))],
        system=_compose_system_prompt(persona.system_prompt),
        max_tokens=2048,
    )
    return PersonaTurn(persona=persona.role, content=resp.content)


async def _run_stage(
    prov: BaseProvider,
    roles: list[PersonaRole],
    personas: dict[PersonaRole, Persona],
    request: CouncilRequest,
    priors: list[PersonaTurn],
) -> list[PersonaTurn]:
    tasks = [
        _run_persona(prov, personas[role], request, priors)
        for role in roles
        if role in personas
    ]
    results = await asyncio.gather(*tasks)
    return list(results)


async def run_council(
    request: CouncilRequest,
    *,
    provider: BaseProvider | None = None,
) -> CouncilResponse:
    """Run council deliberation in staged parallel execution."""
    prov = provider or get_provider()
    personas = {p.role: p for p in load_personas()}
    all_turns: list[PersonaTurn] = []

    for stage in [STAGE_1, STAGE_2, STAGE_3, STAGE_4, STAGE_5]:
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
