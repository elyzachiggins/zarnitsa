# Zarnitsa architecture

## Layers

```
┌──────────────────────────────────────────────────────────────┐
│ Frontend (frontend/) — Vite + vanilla TS                      │
│   Council viewer, chat, prompt-studio (toggle persona sections)│
└──────────────────────────────────────────────────────────────┘
                              │ HTTP
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ API (src/zarnitsa/api/) — FastAPI                              │
│   /v1/chat/completions   OpenAI-compatible, single persona     │
│   /v1/council            full institutional deliberation       │
│   /v1/personas           registry                              │
│   /v1/corpus/search      RAG retrieval (stub)                  │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│ Orchestrator (src/zarnitsa/orchestrator/) — LangGraph          │
│   Cultural prior prefix + persona DAG                          │
│   DELIBERATION_ORDER: GRU → GOU/GOMU/VBpS/TsVSI/Econ → CGS →   │
│                       Sino → MoD → CinC                        │
└──────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        Providers        Personas        Corpus + Provenance
        (cloud/offline)  (10 .md files)  (snapshots/<date>/)
```

## Key design choices

- **Single Python package**, not a monorepo. Package = `zarnitsa`. Frontend is sibling, not subpackage.
- **Personas as markdown files** (`data/personas/*.md`) with YAML frontmatter — editable without Python, version-controlled, diff-friendly.
- **Cultural prior is injected by the orchestrator**, not duplicated in every persona file — keeps personas focused on their institutional role.
- **OpenAI-compatible at `/v1/chat/completions`** so any existing tool (Open-WebUI, LibreChat, OpenAI SDK with custom base_url) can talk to Zarnitsa.
- **Corpus snapshots are dated directories** — `data/corpus/snapshots/2026-05/`. Each snapshot is an immutable knowledge-horizon release. Offline deployments stay on their snapshot until updated.
- **Provenance enforcement is configurable.** `ZARNITSA_FIDELITY_MODE=strict` rejects outputs that fail to cite when making fact-shaped claims. `permissive` allows model-extrapolation but tags it.

## What's stubbed

- LangGraph wiring (`orchestrator/graph.py` has the sequential v0; parallel deliberation comes next)
- Vector retrieval (only keyword overlap today)
- Replay logs / validation pipeline
- Provider implementations beyond Anthropic and Ollama (Gemini, OpenRouter)
- Frontend UI
- Gate / license check on the deployed API

## Next milestones (post-scaffold)

1. Wire the orchestrator into a true LangGraph `StateGraph` with parallel branches and conditional dissent edges.
2. Build the corpus from `GROUNDING for RRTA.docx` into ~60–100 entries via `scripts/extract_corpus_from_docx.py` + manual segmentation pass.
3. Add embedding-based retrieval (`sentence-transformers` with `intfloat/multilingual-e5-large` for Russian) and the hybrid scorer.
4. Wire the provenance enforcement into council output rendering.
5. Build the frontend: chat pane, council deliberation viewer with citation hovers, persona prompt-studio.
6. Validation pipeline: replay logs + ISW-comparison scenarios + expert review checkpoints.
