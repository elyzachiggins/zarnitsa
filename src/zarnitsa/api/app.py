"""FastAPI application factory and route wiring."""

from __future__ import annotations

import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from zarnitsa import __version__
from zarnitsa.api.schemas import (
    OAIChatCompletionRequest,
    OAIChatCompletionResponse,
    OAIChoice,
    OAIMessage,
    OAIUsage,
)
from zarnitsa.exceptions import PersonaError, ProviderError
from zarnitsa.orchestrator import CULTURAL_PRIOR, run_council, run_council_streaming
from zarnitsa.personas import load_persona, load_personas
from zarnitsa.providers import ProviderMessage, get_provider
from zarnitsa.types import CouncilRequest, CouncilResponse, PersonaRole, WargameMode

app = FastAPI(
    title="Zarnitsa",
    description="Institutional Russian decision-modeling council.",
    version=__version__,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/v1/personas")
async def list_personas_endpoint() -> list[dict[str, str]]:
    try:
        return [
            {
                "role": p.role.value,
                "russian_name": p.russian_name,
                "title": p.title,
            }
            for p in load_personas()
        ]
    except PersonaError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/v1/chat/completions", response_model=OAIChatCompletionResponse)
async def chat_completions(req: OAIChatCompletionRequest) -> OAIChatCompletionResponse:
    """OpenAI-compatible single-persona chat. Default persona is the Chief of General Staff."""
    persona_role_str = req.persona or "chief_of_general_staff"
    try:
        role = PersonaRole(persona_role_str)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"unknown persona: {persona_role_str}") from e

    try:
        persona = load_persona(role)
    except PersonaError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    provider = get_provider()
    messages = [ProviderMessage(role=m.role, content=m.content) for m in req.messages]
    system_prompt = f"{CULTURAL_PRIOR}\n\n---\n\n{persona.system_prompt}"

    try:
        resp = await provider.complete(
            messages=messages,
            system=system_prompt,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
        )
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    return OAIChatCompletionResponse(
        model=f"zarnitsa-{persona.role.value}",
        choices=[
            OAIChoice(
                message=OAIMessage(role="assistant", content=resp.content),
                finish_reason=resp.stop_reason or "stop",
            )
        ],
        usage=OAIUsage(
            prompt_tokens=resp.input_tokens,
            completion_tokens=resp.output_tokens,
            total_tokens=resp.input_tokens + resp.output_tokens,
        ),
    )


@app.post("/v1/council", response_model=CouncilResponse)
async def council_deliberate(req: CouncilRequest) -> CouncilResponse:
    """Full institutional council deliberation.

    Currently runs the personas sequentially through DELIBERATION_ORDER. Parallel
    deliberation via LangGraph is the next milestone.
    """
    try:
        return await run_council(req)
    except (PersonaError, ProviderError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/v1/council/stream")
async def council_stream(req: CouncilRequest) -> StreamingResponse:
    """SSE stream — emits each PersonaTurn as JSON the moment it finishes.

    Event shape:  data: {"type": "turn", "turn": {...PersonaTurn...}}\n\n
    Final event:  data: {"type": "done"}\n\n
    Error event:  data: {"type": "error", "message": "..."}\n\n
    """
    async def generate():
        try:
            async for turn in run_council_streaming(req):
                payload = json.dumps({"type": "turn", "turn": turn.model_dump(mode="json")})
                yield f"data: {payload}\n\n"
            yield 'data: {"type": "done"}\n\n'
        except (PersonaError, ProviderError) as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # prevent nginx/Render proxy buffering
        },
    )


@app.post("/v1/corpus/search")
async def corpus_search(query: str, top_k: int = 8) -> list[dict[str, object]]:
    """Stub. Implement with `zarnitsa.corpus.Retriever` once snapshot has real entries."""
    from zarnitsa.corpus import Retriever
    from zarnitsa.exceptions import CorpusError

    try:
        retriever = Retriever()
        hits = retriever.search(query, top_k=top_k)
    except CorpusError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    return [
        {
            "id": entry.id,
            "title": entry.title,
            "tier": entry.tier.value,
            "score": score,
            "snippet": entry.content[:240],
        }
        for entry, score in hits
    ]
