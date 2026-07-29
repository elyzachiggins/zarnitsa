"""LangGraph StateGraph tests.

The point of these is equivalence: the graph and the asyncio path must produce the
same deliberation. If they can diverge, having two execution modes is a liability
rather than a feature.
"""

from __future__ import annotations

import pytest

from zarnitsa.orchestrator import graph as council
from zarnitsa.types import CouncilRequest, PersonaRole

# langgraph is an optional extra; skip the module cleanly rather than erroring when
# it isn't installed. The import below must follow this call.
pytest.importorskip("langgraph", reason="langgraph is an optional dependency")

from zarnitsa.orchestrator.langgraph_council import (
    build_council_graph,
    run_council_graph,
)

SCENARIO = "NATO announces accelerated accession timeline."


def test_graph_compiles() -> None:
    assert build_council_graph() is not None


def test_public_entry_point_no_longer_raises() -> None:
    """build_council_graph() raised NotImplementedError while the README led with it."""
    assert council.build_council_graph() is not None


def test_graph_topology() -> None:
    """GRU fans out to MOD and CGS, which fan back in at SOVBEZ."""
    compiled = build_council_graph()
    nodes = set(compiled.get_graph().nodes)
    for seat in ("retrieve", "gru", "mod", "cgs", "sovbez", "cinc"):
        assert seat in nodes

    edges = {(e.source, e.target) for e in compiled.get_graph().edges}
    assert ("retrieve", "gru") in edges
    assert ("gru", "mod") in edges and ("gru", "cgs") in edges
    assert ("mod", "sovbez") in edges and ("cgs", "sovbez") in edges
    assert ("sovbez", "cinc") in edges


async def test_graph_runs_all_five_seats_in_order(fake_provider) -> None:
    resp = await run_council_graph(CouncilRequest(scenario=SCENARIO), provider=fake_provider)
    assert [t.persona for t in resp.turns] == [
        PersonaRole.GRU,
        PersonaRole.MOD,
        PersonaRole.CGS,
        PersonaRole.SOVBEZ,
        PersonaRole.CINC,
    ]


async def test_graph_matches_asyncio_path(fake_provider) -> None:
    """Both execution modes must produce the same deliberation."""
    from tests.conftest import FakeProvider

    req = CouncilRequest(scenario=SCENARIO)
    via_asyncio = await council.run_council(req, provider=FakeProvider())
    via_graph = await run_council_graph(req, provider=FakeProvider())

    assert [t.persona for t in via_asyncio.turns] == [t.persona for t in via_graph.turns]
    assert via_asyncio.recommendation == via_graph.recommendation
    assert via_asyncio.metadata["grounding"] == via_graph.metadata["grounding"]
    assert via_asyncio.metadata["retrieved_entries"] == via_graph.metadata["retrieved_entries"]


async def test_graph_threads_prior_turns_forward(fake_provider) -> None:
    """CINC must see all four prior seats, same as the asyncio path."""
    await run_council_graph(CouncilRequest(scenario=SCENARIO), provider=fake_provider)
    cinc_prompt = fake_provider.calls[-1]["user"]
    for role in (
        "main_intelligence_directorate",
        "minister_of_defense",
        "chief_of_general_staff",
        "security_council",
    ):
        assert f"Prior council input — {role}" in cinc_prompt


async def test_settings_toggle_routes_through_graph(monkeypatch, fake_provider) -> None:
    monkeypatch.setattr(council.settings, "use_langgraph", True)
    resp = await council.run_council(CouncilRequest(scenario=SCENARIO), provider=fake_provider)
    assert len(resp.turns) == 5
