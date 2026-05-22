# Personas

The institutional council. Each `*.md` file is a single persona definition with YAML frontmatter (role, Russian title, vocabulary, source-tier preferences) and a markdown body containing the system prompt.

| # | File | Role | Russian |
|---|---|---|---|
| 01 | `01_cgs.md` | Chief of General Staff | НГШ |
| 02 | `02_gou.md` | Main Operations Directorate | НГОУ |
| 03 | `03_gomu.md` | Main Org-Mob Directorate | НГОМУ |
| 04 | `04_tsvsi.md` | Center for Military-Strategic Studies | ЦВСИ |
| 05 | `05_gru.md` | Main Intelligence Directorate | ГРУ |
| 06 | `06_vbps.md` | Unmanned Systems Forces | ВБпС |
| 07 | `07_mod.md` | Minister of Defense | МО |
| 08 | `08_cinc.md` | Commander-in-Chief | ВГК |
| 09 | `09_sino_liaison.md` | Sino-Russian liaison (advisor) | — |
| 10 | `10_econ_advisor.md` | Economic advisor (MoF/CBR) | — |

These are **initial drafts**. They will be iterated against (a) expert review by Russian-doctrine analysts and (b) replay-log review of council deliberations on validation scenarios.

Every persona shares a **cultural prior** that is *not* itself a persona — it is injected by the orchestrator into every persona's system prompt:

- *Russkiy mir* as civilizational, not ethno-nationalistic, frame
- Sovereignty (*суверенитет*) as the supreme value
- 1990s humiliation as cautionary memory
- Great Patriotic War (WWII) as foundational memory
- Critique of Western universalism as imperial pretension
- Anti-mirror-imaging — think *from* the Russian perspective, not *about* it

See `src/zarnitsa/orchestrator/cultural_prior.py` for the prefix injection.
