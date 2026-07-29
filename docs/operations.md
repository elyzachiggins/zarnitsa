# Operations

Running Zarnitsa without a surprise bill, and choosing a backbone on evidence.

## First thing to run

```bash
zarnitsa doctor
```

This loads and indexes the corpus for real, loads every persona, runs a retrieval
probe, and reports the security posture. It exits non-zero if anything failed.

Run it after every corpus edit. A single malformed YAML frontmatter block makes
`load_snapshot()` raise, and the orchestrator catches retrieval failures and continues
without grounding — so a broken corpus produces plausible-looking output with no
sources behind it and nothing in the API response says so. `doctor` is the check that
makes that state visible.

## Security

The council endpoints each spend **five model completions** per request. Deployed
publicly with no auth, `/v1/council` is a way for anyone with the URL to spend your
model budget in a loop.

| Setting | Effect |
|---|---|
| `ZARNITSA_API_KEYS` | Comma-separated shared secrets. **Empty means the endpoints are public.** |
| `ZARNITSA_ALLOWED_ORIGINS` | CORS origins. Narrow this in production. |
| `ZARNITSA_RATE_LIMIT_REQUESTS` | Deliberations per caller per window (0 disables). |
| `ZARNITSA_RATE_LIMIT_WINDOW_SECONDS` | Window length, default 3600. |

Clients send `X-API-Key: <key>` or `Authorization: Bearer <key>`. Requests are bucketed
by key when present and by client IP otherwise.

Metered routes: `/v1/council`, `/v1/council/stream`, `/v1/chat/completions`.
`/v1/corpus/search` requires a key but is not rate limited — it makes no model calls.
`/health` and `/v1/personas` are open.

**Two limitations to know about.**

The rate limiter keeps its window in process memory. That is correct for a
single-instance deployment and wrong with multiple workers, where each process keeps
its own counter and the effective limit multiplies. `render.yaml` pins `--workers 1`
for this reason. Moving to more than one worker means moving the window to Redis.

A key compiled into a static frontend is not a secret — anyone can read the bundle. The
frontend therefore reads an optional key from `localStorage` (`zarnitsa.setKey("...")`
in the browser console) rather than embedding one. A genuinely public demo is protected
by the per-IP rate limit, not by a key.

## Cost

One deliberation is five calls at 6–8k `max_tokens`. Because CINC receives every prior
turn in full, a deliberation runs roughly 66k input / 18k output tokens — **output
price dominates**, which inverts the usual model ranking.

Approximate cost per deliberation:

| Backbone | $/deliberation |
|---|---|
| `anthropic:claude-opus-4-7` | ~$0.78 |
| `anthropic:claude-haiku-4-5` | ~$0.16 |
| `openrouter:moonshotai/kimi-k2-thinking` | ~$0.085 |
| `openrouter:deepseek/deepseek-v3.2` | ~$0.025 |

Treat these as starting hypotheses. `zarnitsa eval` reports what you actually spent —
OpenRouter returns real per-request cost, and it is threaded through to
`metadata.usage.cost_usd` on every response.

### Two levers

**Prompt caching** (`ZARNITSA_PROMPT_CACHE`, on by default, Anthropic only). The system
prompt is assembled as two cache-marked blocks: the shared prefix (language rules +
cultural prior), identical across all five seats and every request, then the persona
prompt, stable per seat. Check it is working by reading `cache_read_tokens` in
`metadata.usage` — if it stays zero across repeated requests, something in the prefix
is varying.

**Seat routing.** The four supporting personas mostly produce intermediate analysis
that CINC consumes; CINC writes what the user reads. Route them separately:

```bash
ZARNITSA_BACKBONE=openrouter
ZARNITSA_OPENROUTER_MODEL=deepseek/deepseek-v3.2
ZARNITSA_CINC_BACKBONE=openrouter
ZARNITSA_CINC_MODEL=moonshotai/kimi-k2-thinking
```

## Choosing a backbone

```bash
zarnitsa eval \
  -m openrouter:deepseek/deepseek-v3.2 \
  -m openrouter:moonshotai/kimi-k2-thinking \
  -m anthropic:claude-opus-4-7 \
  --out eval-results.json
```

Every model runs every scenario in `data/eval/scenarios.yaml`, so results are
comparable. The rubric is entirely mechanical — no LLM judge — which makes it
reproducible, free, and defensible:

| Metric | What it catches |
|---|---|
| `Cited` | Fraction of turns citing at least one corpus entry. Low = the model is ignoring its grounding, or retrieval surfaced nothing relevant. |
| `Lang` | Compliance with the English-first rule: no Cyrillic headings, no Cyrillic abbreviations from the banned list, no Cyrillic salutation. |
| `InFrame` | Fraction of turns that stayed in persona instead of breaking to assistant voice ("as an AI", "I cannot"). **This is the one that eliminates candidates.** Models tuned to hedge on adversary modelling fail here regardless of price. |
| `Chars` | Mean output length — catches models that truncate or pad. |
| `Cost $` | Provider-reported actual spend. |

These measure **compliance, not quality**. A model can score 1.0 and still produce
shallow analysis. Use the rubric to eliminate models that fail hard constraints, then
read the survivors' output by hand to choose between them. Write down which you picked
and why — that reasoning is worth more than the table.

Cost note: 3 models × 5 scenarios × 5 seats = 75 completions. The CLI prints the count
and asks for confirmation before spending anything.

## Offline

```bash
docker compose -f docker/offline.yml up
```

Runs against a local Ollama. Prompt-cache flags are ignored (no such API), and the
per-seat routing still applies if you point the two backbones at different local models.

---

## Grounding status (added in the resilience pass)

Every response now reports whether it actually had source material behind it, in
`metadata.grounding` and as the first SSE event.

| Status | Meaning | Behaviour |
|---|---|---|
| `grounded` | Full corpus, entries retrieved | Normal |
| `degraded` | Some entries failed to load; retrieval ran over a partial corpus | Warning surfaced; run proceeds |
| `no_match` | Corpus fine, nothing matched this scenario | Warning surfaced; run proceeds |
| `corpus_unavailable` | Corpus could not be loaded at all | **503** unless `ZARNITSA_REQUIRE_GROUNDING=false` |

`no_match` is normal — an obscure scenario legitimately retrieves nothing, and the
council can still reason from its institutional priors. `corpus_unavailable` is not,
and the default is to refuse rather than return analysis that reads as
corpus-supported but isn't.

Two changes back this up:

- **One bad entry no longer takes the corpus down.** `load_snapshot` reports per-file
  failures instead of aborting on the first, and raises only when *nothing* loaded.
- **`/health` reports corpus state**, so a monitor catches a broken snapshot without
  waiting for a user to notice.

## Claim verification

`metadata.verification` runs a lexical support screen over every sentence that names a
cited entry. It is free, deterministic, and **weak on purpose** — read the caveat it
returns.

What it proves: the claim shares substantial vocabulary with the entry it cites.
What it does not prove: that the entry supports the claim.

**On this corpus it usually cannot run at all.** Personas write in English (the
language rule requires it) while most corpus entries are Russian source text, and word
overlap across scripts is near zero whether or not the citation is sound. Those pairs
are reported as `not_assessed` and excluded from `support_rate` — which is `null`, not
`0.0`, when nothing was assessable. A screen that flagged every cross-lingual citation
as unsupported would fire on everything and teach you to ignore it.

Meaningful cross-lingual claim checking needs the multilingual embedding path, not word
overlap. That is the honest next step here, and it is not done.

## Optional backends

All three are off by default. Each is a config change, not a rewrite.

| Setting | Default | Turn on when |
|---|---|---|
| `ZARNITSA_RETRIEVAL_MODE=hybrid` | `bm25` | Corpus past a few hundred entries, or you need cross-lingual matching. Needs `pip install -e ".[offline]"`. |
| `ZARNITSA_USE_LANGGRAPH=true` | off | You want checkpointing or node-level streaming. Needs `.[graph]`. Same output either way. |
| `ZARNITSA_REDIS_URL=redis://...` | unset | More than one worker. The in-process limiter keeps its window in local memory, so N workers means N counters. Needs `.[redis]`. |
