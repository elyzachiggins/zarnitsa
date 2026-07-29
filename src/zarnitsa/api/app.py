"""FastAPI application factory and route wiring."""

from __future__ import annotations

import json
import logging

from fastapi import Depends, FastAPI, HTTPException, Query
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
from zarnitsa.api.security import rate_limit, require_api_key
from zarnitsa.config import settings
from zarnitsa.exceptions import (
    CorpusError,
    CorpusUnavailable,
    PersonaError,
    ProviderError,
)
from zarnitsa.orchestrator import CULTURAL_PRIOR, run_council, run_council_streaming
from zarnitsa.orchestrator.grounding import Grounding
from zarnitsa.personas import load_persona, load_personas
from zarnitsa.providers import ProviderMessage, get_provider
from zarnitsa.types import CouncilRequest, CouncilResponse, PersonaRole

log = logging.getLogger(__name__)

app = FastAPI(
    title="Zarnitsa",
    description="Institutional Russian decision-modeling council.",
    version=__version__,
)

# A wildcard origin is only safe because the expensive routes below sit behind an
# API key. If ZARNITSA_API_KEYS is unset, allow_origins should be narrowed too —
# wildcard CORS plus no auth means any page on the internet can spend your budget.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

# Routes that trigger model calls. Order matters: the key check populates the
# identity the limiter buckets on.
_METERED = [Depends(require_api_key), Depends(rate_limit)]


@app.get("/health")
async def health() -> dict[str, object]:
    """Liveness plus corpus state.

    Reports corpus health so a monitor can catch a broken snapshot without waiting
    for a user to notice their analysis has no sources behind it.
    """
    corpus: dict[str, object]
    try:
        from zarnitsa.corpus import Retriever

        retriever = Retriever()
        corpus = {
            "entries": len(retriever),
            "failed": [str(e) for e in retriever.errors],
            "ok": not retriever.errors and len(retriever) > 0,
        }
    except Exception as e:
        corpus = {"entries": 0, "failed": [str(e)], "ok": False}

    return {
        "status": "ok" if corpus["ok"] else "degraded",
        "version": __version__,
        "auth_required": settings.auth_required,
        "corpus": corpus,
    }


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


@app.post(
    "/v1/chat/completions",
    response_model=OAIChatCompletionResponse,
    dependencies=_METERED,
)
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


@app.post("/v1/council", response_model=CouncilResponse, dependencies=_METERED)
async def council_deliberate(req: CouncilRequest) -> CouncilResponse:
    """Full institutional council deliberation across four staged rounds.

    Returns 503 when the corpus cannot be loaded. That is deliberate: ungrounded
    output is indistinguishable from grounded output to a reader, so the failure is
    surfaced rather than absorbed. Set ZARNITSA_REQUIRE_GROUNDING=false to override.
    """
    try:
        return await run_council(req)
    except CorpusUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except (PersonaError, ProviderError) as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/v1/council/stream", dependencies=_METERED)
async def council_stream(req: CouncilRequest) -> StreamingResponse:
    """SSE stream — emits each PersonaTurn as JSON the moment it finishes.

    Event shape:  data: {"type": "turn", "turn": {...PersonaTurn...}}\n\n
    Final event:  data: {"type": "done"}\n\n
    Error event:  data: {"type": "error", "message": "..."}\n\n
    """

    async def generate():
        try:
            async for item in run_council_streaming(req):
                if isinstance(item, Grounding):
                    # Emitted before any analysis so the client can show a caveat
                    # first, rather than after the user has already read the output.
                    payload = json.dumps({"type": "grounding", "grounding": item.to_dict()})
                else:
                    payload = json.dumps(
                        {"type": "turn", "turn": item.model_dump(mode="json")}
                    )
                yield f"data: {payload}\n\n"
            yield 'data: {"type": "done"}\n\n'
        except CorpusUnavailable as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        except (PersonaError, ProviderError) as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        except Exception:
            # The response has already begun, so an unhandled exception here would
            # otherwise close the stream with no terminal event and leave the client
            # spinning until its own timeout fires.
            log.exception("council stream failed")
            yield (
                'data: {"type": "error", "message": '
                '"internal error during deliberation"}\n\n'
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # prevent nginx/Render proxy buffering
        },
    )


@app.get("/v1/corpus/search", dependencies=[Depends(require_api_key)])
async def corpus_search(
    query: str = Query(..., min_length=1),
    top_k: int = Query(8, ge=1, le=50),
) -> list[dict[str, object]]:
    """Rank corpus entries against a query. No model calls, so no rate limit."""
    from zarnitsa.corpus import Retriever

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
            "score": round(score, 4),
            "snippet": entry.content[:240],
        }
        for entry, score in hits
    ]
