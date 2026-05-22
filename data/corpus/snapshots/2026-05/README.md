# Corpus snapshot 2026-05

**Knowledge horizon: 2026-05-22.**

Each `*.md` file is a single corpus entry — atomic, citeable, with YAML frontmatter that the loader (`zarnitsa.corpus.entry.CorpusEntry`) parses into a structured object.

## Frontmatter schema

```yaml
id: 2014-doctrine-art-12              # stable identifier (also the cite key)
title: 2014 Military Doctrine, Article 12 (External Threats)
tier: primary_doctrine                # one of the SourceTier enum values
source_date: 2014-12-26               # ISO date of the source
source_citation: "Военная доктрина РФ, утв. 25.12.2014, ст. 12"
language: ru                          # iso-639-1
keywords: [НАТО, расширение, угроза, внешняя]
topics: [doctrine, threats, external]
cited_by_personas:
  - chief_of_general_staff
  - center_military_strategic
```

## Source tiers (in order of authority for adversary modeling)

1. `primary_doctrine` — official doctrine, federal laws, presidential decrees on defense
2. `kremlin_statement` — speeches, addresses, press conferences of the President, MoD, Foreign Minister
3. `academic_russian` — Voyennaya Mysl, VAGSh publications, Russian policy-research institutes (RIAC, CFDP)
4. `russian_state_media` — RIA, TASS, RT (used cautiously, mostly for incident attribution and elite messaging)
5. `russian_milblogger` — Rybar, Voyennyi Osvedomitel, ChVK Medved, Two Majors (fast but uneven; high signal on lessons-learned)
6. `osint_analysis` — ISW, RUSI, CNAS, CSIS, FPRI, Jamestown, Carnegie (Western analytical lens — useful for what the adversary sees)
7. `model_extrapolation` — LLM-generated reasoning without direct corpus support; **always marked**

## Initial population

This snapshot is a **stub**. The seed corpus is the user's `GROUNDING for RRTA.docx` extracted into ~60–100 entries by the corpus prep pipeline (`scripts/extract_corpus_from_docx.py`, TODO).

See `01_sample_entry.md` for the format.
