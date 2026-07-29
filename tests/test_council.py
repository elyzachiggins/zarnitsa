"""Orchestrator tests — the four-stage DAG, run against a fake provider."""

from __future__ import annotations

import pytest

from zarnitsa.orchestrator.graph import (
    _MAX_TOKENS_CINC,
    _MAX_TOKENS_DEFAULT,
    _compose_system_prompt,
    _retrieve,
    run_council,
    run_council_streaming,
)
from zarnitsa.orchestrator.grounding import Grounding
from zarnitsa.types import CouncilRequest, PersonaRole, WargameMode

SCENARIO = "NATO announces accelerated Ukrainian accession timeline."


@pytest.fixture
def request_() -> CouncilRequest:
    return CouncilRequest(scenario=SCENARIO)


async def test_council_runs_all_five_seats_in_order(request_, fake_provider) -> None:
    resp = await run_council(request_, provider=fake_provider)
    assert [t.persona for t in resp.turns] == [
        PersonaRole.GRU,
        PersonaRole.MOD,
        PersonaRole.CGS,
        PersonaRole.SOVBEZ,
        PersonaRole.CINC,
    ]


async def test_recommendation_comes_from_cinc(request_, fake_provider) -> None:
    resp = await run_council(request_, provider=fake_provider)
    cinc = next(t for t in resp.turns if t.persona == PersonaRole.CINC)
    assert resp.recommendation == cinc.content


async def test_cinc_gets_larger_token_budget(request_, fake_provider) -> None:
    await run_council(request_, provider=fake_provider)
    budgets = [c["max_tokens"] for c in fake_provider.calls]
    assert budgets[:4] == [_MAX_TOKENS_DEFAULT] * 4
    assert budgets[4] == _MAX_TOKENS_CINC


async def test_later_stages_see_earlier_turns(request_, fake_provider) -> None:
    """CINC must receive all four prior turns; GRU must receive none."""
    await run_council(request_, provider=fake_provider)
    assert "Prior council input" not in fake_provider.calls[0]["user"]
    cinc_prompt = fake_provider.calls[4]["user"]
    for role in ("main_intelligence_directorate", "minister_of_defense",
                 "chief_of_general_staff", "security_council"):
        assert f"Prior council input — {role}" in cinc_prompt


async def test_corpus_context_reaches_every_persona(request_, fake_provider) -> None:
    """The grounding block is the whole point; its absence was invisible for months."""
    await run_council(request_, provider=fake_provider)
    for call in fake_provider.calls:
        assert "# Corpus — retrieved grounding material" in call["user"]


async def test_retrieval_runs_once_not_per_persona(request_, fake_provider) -> None:
    """All five prompts must carry the byte-identical corpus block.

    Retrieval depends only on the scenario, so a per-persona re-query would be pure
    waste. Comparing the rendered block is the observable proxy for that.
    """
    from zarnitsa.orchestrator.graph import _format_corpus_context

    await run_council(request_, provider=fake_provider)
    retrieved, _ = _retrieve(request_)
    expected = _format_corpus_context(retrieved)
    assert expected, "expected a non-empty corpus block"
    for call in fake_provider.calls:
        assert expected in call["user"]


async def test_citations_are_populated_when_persona_cites(request_) -> None:
    from tests.conftest import FakeProvider

    retrieved, _ = _retrieve(CouncilRequest(scenario=SCENARIO))
    assert retrieved, "expected the scenario to retrieve something"
    cited_id = retrieved[0][0].id

    provider = FakeProvider(reply=f"Assessment grounded in {cited_id} as required.")
    resp = await run_council(CouncilRequest(scenario=SCENARIO), provider=provider)
    assert all(t.citations for t in resp.turns)
    assert resp.turns[0].citations[0].entry_id == cited_id


async def test_metadata_reports_usage_and_retrieval(request_, fake_provider) -> None:
    resp = await run_council(request_, provider=fake_provider)
    usage = resp.metadata["usage"]
    assert usage["input_tokens"] == 500  # 5 seats x 100
    assert usage["output_tokens"] == 250
    assert resp.metadata["retrieved_entries"]


async def test_streaming_yields_grounding_first_then_turns(request_, fake_provider) -> None:
    """Grounding must precede any analysis so a caveat can render before output."""
    items = [i async for i in run_council_streaming(request_, provider=fake_provider)]
    assert isinstance(items[0], Grounding)
    seen = [i.persona for i in items[1:]]
    assert seen[0] == PersonaRole.GRU
    assert seen[-1] == PersonaRole.CINC
    assert len(seen) == 5


# --- prompt shape ----------------------------------------------------------


def test_system_prompt_has_two_cache_breakpoints() -> None:
    blocks = _compose_system_prompt("PERSONA BODY")
    assert len(blocks) == 2
    assert all(b.cache for b in blocks)


def test_shared_prefix_is_identical_across_personas() -> None:
    """The first block must be byte-identical, or the shared cache never hits."""
    a = _compose_system_prompt("persona A")[0].text
    b = _compose_system_prompt("persona B")[0].text
    assert a == b


def test_persona_body_is_in_second_block() -> None:
    blocks = _compose_system_prompt("UNIQUE_PERSONA_MARKER")
    assert "UNIQUE_PERSONA_MARKER" not in blocks[0].text
    assert "UNIQUE_PERSONA_MARKER" in blocks[1].text


@pytest.mark.parametrize("mode", list(WargameMode))
async def test_every_wargame_mode_emits_instructions(mode, fake_provider) -> None:
    """STRATEGIC is the default and previously had no header at all."""
    await run_council(
        CouncilRequest(scenario=SCENARIO, wargame_mode=mode), provider=fake_provider
    )
    prompt = fake_provider.calls[0]["user"]
    assert ("# Wargame mode" in prompt) or ("# Mode —" in prompt), f"{mode} has no header"
