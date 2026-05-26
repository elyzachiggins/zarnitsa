"""Council deliberation DAG.

Flow:
    INTAKE
      └─> GRU (intel assessment)
             └─> parallel: GOU, GOMU, VBpS, TsVSI, Econ
                    └─> CGS (synthesis)
                           └─> MoD (political-military review, incl. Sino liaison)
                                  └─> CinC (strategic vector, red lines, authorization)
                                         └─> OUTPUT

This module wires personas to LangGraph nodes. The current implementation is a stub
that runs sequentially; the parallel branch will be implemented with langgraph.Send
in a follow-up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from zarnitsa.orchestrator.cultural_prior import CULTURAL_PRIOR
from zarnitsa.personas import load_personas
from zarnitsa.providers import ProviderMessage, get_provider
from zarnitsa.types import CouncilRequest, CouncilResponse, PersonaRole, PersonaTurn, WargameMode

if TYPE_CHECKING:
    from zarnitsa.providers.base import BaseProvider

DELIBERATION_ORDER: list[PersonaRole] = [
    PersonaRole.GRU,
    PersonaRole.GOU,
    PersonaRole.GOMU,
    PersonaRole.VBPS,
    PersonaRole.TSVSI,
    PersonaRole.ECON_ADVISOR,
    PersonaRole.CGS,
    PersonaRole.SINO_LIAISON,
    PersonaRole.MOD,
    PersonaRole.CINC,
]


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


def _mode_instruction(mode: WargameMode, role: PersonaRole) -> str:
    return _MODE_HEADERS.get(mode, "")


async def run_council(
    request: CouncilRequest,
    *,
    provider: BaseProvider | None = None,
) -> CouncilResponse:
    """Run a council deliberation sequentially through the persona DAG.

    This is the v0 implementation. v1 will use LangGraph's StateGraph with
    parallel branches and conditional edges.
    """
    prov = provider or get_provider()
    personas = {p.role: p for p in load_personas()}
    turns: list[PersonaTurn] = []

    for role in DELIBERATION_ORDER:
        persona = personas.get(role)
        if persona is None:
            continue

        priors = _format_priors(turns)
        user_msg_parts = [f"# Scenario\n\n{request.scenario}"]
        if request.cinc_intent:
            user_msg_parts.append(f"# CinC stated intent\n\n{request.cinc_intent}")
        if request.constraints:
            user_msg_parts.append("# Constraints\n\n" + "\n".join(f"- {c}" for c in request.constraints))
        if priors:
            user_msg_parts.append(priors)
        mode_instruction = _mode_instruction(request.wargame_mode, persona.role)
        if mode_instruction:
            user_msg_parts.append(mode_instruction)
        user_msg_parts.append(
            f"# Your turn\n\nSpeak now as {persona.title} ({persona.russian_name}). "
            "Follow your defined output format. Be specific. Mark fidelity."
        )
        user_msg = "\n\n".join(user_msg_parts)

        resp = await prov.complete(
            messages=[ProviderMessage(role="user", content=user_msg)],
            system=_compose_system_prompt(persona.system_prompt),
            max_tokens=2048,
            temperature=0.6,
        )
        turns.append(PersonaTurn(persona=role, content=resp.content))

    final = turns[-1].content if turns else "No deliberation."

    return CouncilResponse(
        recommendation=final,
        courses_of_action=[],
        dissents=[],
        turns=turns,
        knowledge_horizon=None,
        metadata={"wargame_mode": request.wargame_mode.value, "personas_engaged": [t.persona.value for t in turns]},
    )


def build_council_graph() -> Any:
    """Return a compiled LangGraph for the council flow.

    TODO: replace `run_council` once parallel deliberation, conditional dissent,
    and replay-log capture are implemented as graph features.
    """
    raise NotImplementedError("LangGraph wiring is the next milestone — see graph.py docstring")
