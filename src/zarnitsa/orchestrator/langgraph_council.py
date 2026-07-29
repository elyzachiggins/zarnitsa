"""LangGraph StateGraph implementation of the council DAG.

The README has always described Zarnitsa as LangGraph-orchestrated, while
`build_council_graph()` raised NotImplementedError and the real work was done by
hand-rolled staged `asyncio.gather` calls. This makes the claim true.

The DAG:

    retrieve ──> gru ──┬──> mod ────┬──> sovbez ──> cinc ──> END
                       └──> cgs ────┘

MOD and CGS run concurrently and fan back in at SOVBEZ. That fan-in is the reason
`turns` is annotated with `operator.add`: two branches write to the same key in the
same superstep, and without a reducer LangGraph raises InvalidUpdateError rather than
silently picking one.

**This is not the default execution path.** `asyncio.gather` already expressed this
DAG correctly in a tenth of the code, and adding LangGraph to the request path means a
large transitive dependency tree in every deploy for no behavioural gain. What the
graph buys is introspection — checkpointing, streaming node transitions, visualisation
of the topology — which matters for a writeup and for debugging, not for serving.

So: both paths call the *same* node functions from `graph.py`. They cannot drift,
because there is only one implementation of what a persona turn does. Enable with
ZARNITSA_USE_LANGGRAPH=true.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, StateGraph

from zarnitsa.orchestrator import graph as council
from zarnitsa.orchestrator.grounding import Grounding
from zarnitsa.personas import load_personas
from zarnitsa.personas.loader import Persona
from zarnitsa.providers.base import BaseProvider
from zarnitsa.types import CouncilRequest, CouncilResponse, PersonaRole, PersonaTurn


class CouncilState(TypedDict, total=False):
    """State threaded through the graph.

    `turns` uses operator.add so the parallel MOD/CGS branches merge instead of
    clobbering one another.
    """

    request: CouncilRequest
    provider: BaseProvider | None
    personas: dict[PersonaRole, Persona]
    retrieved: list[tuple[Any, float]]
    grounding: Grounding
    corpus_context: str
    turns: Annotated[list[PersonaTurn], operator.add]


def _ordered(turns: list[PersonaTurn]) -> list[PersonaTurn]:
    """Restore canonical seat order.

    Parallel branches merge in completion order, which is nondeterministic. The
    council has a fixed protocol order and the UI renders in that order, so sort by
    the stage definition rather than by whichever model replied first.
    """
    rank = {role: i for i, role in enumerate(r for stage in council.STAGES for r in stage)}
    return sorted(turns, key=lambda t: rank.get(t.persona, 99))


async def _retrieve_node(state: CouncilState) -> CouncilState:
    retrieved, grounding = council._retrieve(state["request"])
    council._check_grounding(grounding)
    return {
        "retrieved": retrieved,
        "grounding": grounding,
        "corpus_context": council._format_corpus_context(retrieved),
        "personas": {p.role: p for p in load_personas()},
    }


def _seat_node(role: PersonaRole):
    """Build a node that runs one council seat.

    Delegates to council._run_persona — the same function the asyncio path uses — so
    the two execution modes cannot diverge in behaviour.
    """

    async def node(state: CouncilState) -> CouncilState:
        personas = state["personas"]
        if role not in personas:
            return {"turns": []}
        provider = state.get("provider") or council.get_provider_for(role)
        max_tokens = (
            council._MAX_TOKENS_CINC
            if role == PersonaRole.CINC
            else council._MAX_TOKENS_DEFAULT
        )
        turn = await council._run_persona(
            provider,
            personas[role],
            state["request"],
            # Prior turns in protocol order, matching what the asyncio path passes.
            _ordered(state.get("turns", [])),
            state["retrieved"],
            state["corpus_context"],
            max_tokens=max_tokens,
        )
        return {"turns": [turn]}

    return node


def build_council_graph() -> Any:
    """Compile and return the council StateGraph.

    Returns a compiled LangGraph app. `ainvoke({"request": ..., "provider": ...})`
    runs a full deliberation; `astream` yields per-node state updates.
    """
    builder = StateGraph(CouncilState)

    builder.add_node("retrieve", _retrieve_node)
    builder.add_node("gru", _seat_node(PersonaRole.GRU))
    builder.add_node("mod", _seat_node(PersonaRole.MOD))
    builder.add_node("cgs", _seat_node(PersonaRole.CGS))
    builder.add_node("sovbez", _seat_node(PersonaRole.SOVBEZ))
    builder.add_node("cinc", _seat_node(PersonaRole.CINC))

    builder.set_entry_point("retrieve")
    builder.add_edge("retrieve", "gru")
    # Fan out: MOD and CGS deliberate concurrently on the GRU brief.
    builder.add_edge("gru", "mod")
    builder.add_edge("gru", "cgs")
    # Fan in: SOVBEZ waits for both before synthesising.
    builder.add_edge("mod", "sovbez")
    builder.add_edge("cgs", "sovbez")
    builder.add_edge("sovbez", "cinc")
    builder.add_edge("cinc", END)

    return builder.compile()


_compiled: Any | None = None


def _get_compiled() -> Any:
    global _compiled
    if _compiled is None:
        _compiled = build_council_graph()
    return _compiled


async def run_council_graph(
    request: CouncilRequest,
    *,
    provider: BaseProvider | None = None,
) -> CouncilResponse:
    """Run a deliberation through the StateGraph. Same response shape as run_council."""
    final_state = await _get_compiled().ainvoke(
        {"request": request, "provider": provider, "turns": []}
    )
    turns = _ordered(final_state.get("turns", []))
    return council._assemble_response(
        request, turns, final_state["grounding"], final_state.get("retrieved")
    )
