# ZARNITSA

An institutional decision-modeling system that simulates the deliberative apparatus of the Russian Federation Armed Forces through a multi-persona council. Intended for OPFOR red-team use, small-unit threat-intelligence training, and strategic "what would Russia do" advisory.

> **Adversary modeling, not objective analysis.** Zarnitsa models the institutional worldview, doctrinal vocabulary, and decision-making patterns of the Russian General Staff and adjacent bodies. The output reflects the perspective those institutions would produce — it is not a neutral or balanced analysis of any situation. Use it for adversary modeling, training, and red-cell wargaming. Do not use it as a stand-in for independent strategic analysis.

---

## What it does

Given a strategic, operational, or tactical question, Zarnitsa runs a deliberative council of personas representing the major bodies in the Russian military decision-making apparatus:

- **Chief of General Staff** (НГШ) — final military synthesis
- **Chief, Main Operations Directorate** (НГОУ) — operational planning
- **Chief, Main Org-Mobilization Directorate** (НГОМУ) — force structure, mobilization
- **Chief, Center for Military-Strategic Studies** (ЦВСИ) — long-horizon, breakthrough concepts
- **Chief, GRU** — adversary assessment, reflexive control
- **Commander, Unmanned Systems Forces** (ВБпС) — UAV warfighting, Ukraine-learned innovations
- **Minister of Defense** — political-military, war economy
- **Commander-in-Chief** (ВГК) — strategic intent, red lines
- **Sino-Russian liaison** (advisor) — China factor
- **MoF/CBR economic advisor** — inflation, industrial capacity, sanctions

Each persona reasons within a shared cultural prior (Russkiy mir, civilization-state framing, sovereignty as supreme value, anti-Western imperial-universalism critique). Each output carries provenance tags linking claims back to corpus entries by tier.

## Use cases

- **OPFOR red team** in wargaming exercises (small unit through theater)
- **Threat-intelligence training** for service members studying adversary behavior
- **"What would Russia do" advisory** for strategic planners (with appropriate skepticism)
- **Doctrine education** with citation-traceable answers

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

**Pre-MVP scaffolding.** APIs are stubs; only `/v1/chat/completions` with a single persona is operational. See [docs/architecture.md](docs/architecture.md) for the full design and [docs/personas.md](docs/personas.md) for persona definitions.

## Quickstart (development)

```bash
# Python 3.11+
uv sync                        # or: pip install -e ".[dev]"
cp .env.example .env           # add your ANTHROPIC_API_KEY
zarnitsa serve                 # FastAPI on http://localhost:8000
# OpenAPI docs at http://localhost:8000/docs
```

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
