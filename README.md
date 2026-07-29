# ZARNITSA

A system that simulates the military and strategic decision-making apparatus of the Russian Federation through a multi-agent council grounded in a retrieval corpus of Russian military doctrine. Intended for OPFOR red-team use and strategic advisory wargaming.

> **Adversary modeling, not objective analysis.** Zarnitsa models the institutional worldview, doctrinal vocabulary, and decision-making patterns of the Russian General Staff and adjacent bodies. The output reflects the perspective those institutions would produce — it is not a neutral or balanced analysis of any situation. Use it for adversary modeling, training, and red-cell wargaming. Do not use it as a stand-in for independent strategic analysis.

---

## What it does

Given a strategic, operational, or tactical question, Zarnitsa runs a deliberative council of personas representing the major bodies in the Russian military decision-making apparatus:

- **Chief, GRU** — adversary assessment, reflexive control
- **Chief of General Staff** (НГШ) — final military synthesis
- **Security Council** (Совбез)-civilian security interagency apparatus 
- **Minister of Defense** — political-military, war economy
- **Commander-in-Chief** (ВГК) — strategic intent, red lines


Each persona reasons within a shared cultural prior (Russkiy mir, civilization-state framing, sovereignty as supreme value, anti-Western imperial-universalism critique). Each output carries provenance tags linking claims back to corpus entries by tier.

## Use cases

- **Russia Red Team simulation/advisory** for strategic scenarios (with appropriate skepticism)
- **OPFOR red team** in wargaming exercises (small unit through theater)
- **Threat-intelligence training** for service members studying adversary behavior

## Architecture

```
Frontend (Vite + vanilla TS)
        │
        ▼
FastAPI server  ── OpenAI-compatible /v1/chat/completions
                ── /v1/council        (full institutional deliberation)
                ── /v1/opfor          (tactical adversary mode)
                ── /v1/wargame/turn   (formal MDMP-adjacent turn)
                ── /v1/corpus/search  (RAG retrieval)
        │
        ▼
LangGraph orchestrator (stateful DAG, replayable)
        │
        ▼
Backbone (pluggable)
   ├── ONLINE  : Anthropic Claude (default), Gemini, OpenRouter
   └── OFFLINE : Gemma 4 26B MoE (default), Qwen 3.5 72B (heavy), Gemma 4 E4B (light) via Ollama

Knowledge layer
   ├── Corpus: doctrine + Putin/Gerasimov/Belousov speeches + Ukraine lessons +
   │           Unmanned Systems updates + Russian economic posture + China bloc
   ├── Hybrid retrieval: keyword + vector
   └── Provenance engine: every claim tagged
       (primary_doctrine | kremlin_statement | academic_russian |
        russian_state_media | russian_milblogger | osint_analysis | model_extrapolation)
```

## Status

**Pre-MVP.** Operational: `/v1/council` and `/v1/council/stream` (full five-seat
deliberation, corpus-grounded, with citations), `/v1/chat/completions` (single
persona), `/v1/corpus/search`, `/v1/personas`.

Not yet implemented: `build_council_graph()` — the deliberation DAG is hand-rolled
staged `asyncio`, not a LangGraph `StateGraph`.

See [docs/architecture.md](docs/architecture.md) for the design,
[docs/personas.md](docs/personas.md) for persona definitions, and
[docs/operations.md](docs/operations.md) for security, cost, and backbone selection.

## Quickstart (development)

```bash
# Python 3.11+
uv sync                        # or: pip install -e ".[dev]"
cp .env.example .env           # add your ANTHROPIC_API_KEY
zarnitsa doctor                # verify corpus, personas, keys, security posture
zarnitsa serve                 # FastAPI on http://localhost:8000
# OpenAPI docs at http://localhost:8000/docs
```

**Run `zarnitsa doctor` after every corpus edit.** One malformed YAML frontmatter
block makes the whole snapshot fail to load, and because the orchestrator catches
retrieval errors and continues, the result is confident-looking output with no
grounding behind it and nothing in the response to indicate it.

### Before deploying anywhere public

Set `ZARNITSA_API_KEYS`. Each council request spends five model completions; an
unauthenticated public endpoint is a way for strangers to spend your model budget.
See [docs/operations.md](docs/operations.md).

### Cost

A deliberation is five calls at 6–8k `max_tokens`, so **output price dominates**:
roughly $0.78 on `claude-opus-4-7` versus ~$0.025 on `deepseek/deepseek-v3.2` via
OpenRouter. Seats can be routed independently — cheap models for the four supporting
personas, a stronger one for the Commander-in-Chief synthesis. Compare backbones on
evidence with `zarnitsa eval`.

## Offline deployment

```bash
# Pull Gemma 4 26B MoE via Ollama
ollama pull gemma4:26b-moe

# Run Zarnitsa in offline mode
docker-compose -f docker/offline.yml up
```

See [docs/deployment.md](docs/deployment.md) for air-gapped deployment.

## License

[MIT](LICENSE). The *code* is open. The *deployed service* is gated — see [docs/distribution.md](docs/distribution.md) for why and how.

## Acknowledgments

Predecessor: [Colonel General](https://github.com/jeranaias/colonel-general) — the single-persona educational artifact this project supersedes.
