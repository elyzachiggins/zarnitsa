# Council personas

See `data/personas/` for the canonical definitions. This doc is the human-readable index.

## Council members (8)

1. **Chief of General Staff (НГШ)** — `chief_of_general_staff`
   Final military synthesizer. Integrates the directorates into a unified COA recommendation.

2. **Chief, Main Operations Directorate (НГОУ)** — `main_operations_directorate`
   The actual planning brain. Produces *замысел*, force grouping, phasing, fires plan.

3. **Chief, Main Org-Mob Directorate (НГОМУ)** — `main_org_mob_directorate`
   Force structure and mobilization reality. The arithmetic floor under operational ambition.

4. **Chief, Center for Military-Strategic Studies (ЦВСИ)** — `center_military_strategic`
   Long-horizon, breakthrough concepts, escalation dynamics. The forward-looking research voice.

5. **Chief, Main Intelligence Directorate (ГРУ / ГУ ГШ)** — `main_intelligence_directorate`
   Adversary assessment, COG analysis, reflexive control opportunities, maskirovka requirements.

6. **Commander, Unmanned Systems Forces (ВБпС)** — `unmanned_systems_forces`
   New branch (formed Nov 2025). UAV/autonomous integration across the fight, Ukraine-learned.

7. **Minister of Defense (МО)** — `minister_of_defense`
   Belousov archetype. Political-military, defense industrial base, war economy.

8. **Commander-in-Chief (ВГК)** — `commander_in_chief`
   Putin archetype. Strategic vector, red lines, civilizational framing, authorization.

## Advisors (2)

9. **Sino-Russian liaison** — `sino_russian_liaison`
   The China factor. Beijing tolerances, SCO/BRICS context, economic-technical dependencies.

10. **Economic advisor (MoF/CBR)** — `economic_advisor`
    War economy, inflation, defense-industrial capacity, sanctions exposure.

## Deliberation flow

```
INTAKE  (scenario + CinC intent + constraints)
   │
   ▼
[5]  GRU — adversary picture, COG, reflexive opportunities, maskirovka
   │
   ▼
[2,3,6,4,10]  Parallel assessment:
              • GOU — operational options
              • GOMU — force availability, mob implications
              • VBpS — UAV/autonomous contribution
              • TsVSI — long-horizon framing, escalation
              • Econ — cost and sustainability
   │
   ▼
[1]  CGS — synthesis, 2–3 COAs with risks, recommended COA
   │
   ▼
[9]  Sino-Russian liaison — China factor review
   │
   ▼
[7]  MoD — political-military review, CinC framing
   │
   ▼
[8]  CinC — strategic vector, red lines, authorization
   │
   ▼
OUTPUT  (recommendation + COAs + dissents + provenance trail)
```

In the v0 orchestrator (`zarnitsa.orchestrator.graph.run_council`), the deliberation runs
sequentially through `DELIBERATION_ORDER`. The v1 LangGraph implementation will execute the
parallel assessment branch concurrently.

## Cultural prior

All personas share a non-negotiable cultural prior injected by the orchestrator —
see `src/zarnitsa/orchestrator/cultural_prior.py`. The prior is the anti-mirror-imaging
floor: sovereignty as supreme value, *русский мир* as civilizational frame, 1990s as
cautionary memory, WWII as foundational memory, Western universalism critique, and
explicit instruction to reason *from* the Russian institutional perspective rather than
*about* it. Editing the cultural prior changes every persona's behavior.
