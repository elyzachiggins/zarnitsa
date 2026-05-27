# RRTA Practicum Plan — Summer 2026

**Researcher:** Elyza Higgins | **Project:** ZARNITSA (Russian Red Team Agent)

---

## I. Week 1 — Research Design & Literature Foundation
- Write one-page research design statement (3 RQs, scope, limitations)
- Literature review: AI in wargaming, LLM limits, OPFOR realism requirements, mirror-imaging problem
- Identify 3–5 SMEs (Russia analysts, wargame facilitators) for Week 8 external review
- Document ZARNITSA baseline state
- **Deliverable:** Annotated bibliography (20–30 sources); research design statement

## II. Week 2 — System Baseline Audit
- Audit all 10 persona files: pre-war assumptions, institutional specificity gaps, output format issues
- Audit all 30 corpus entries: text quality, coverage gaps, prioritized new entries list
- Run system against 3 known-outcome scenarios (Feb 24 2022 SVO launch; Sep 2022 partial mobilization; Nov 2022 Kherson withdrawal) — document generic/mirror-imaging outputs
- Identify missing source documents: Putin Feb 24 address, Sep 2024 nuclear deterrence update, Maritime Doctrine, NSS update
- **Deliverable:** System audit memo (gaps by persona, corpus, behavioral fidelity)

## III. Week 3 — Doctrinal Analysis: Tactical & Operational
- Drone warfare and VBpS: FPV saturation, Lancet employment, Geran/Shahed, EW-drone coevolution, VBpS as service branch (Nov 2025)
- Failure of initial operational concept: shift from blitzkrieg to attritional grinding, штурмовые группы, deep fires over maneuver
- C2 failures and adaptations: battalion-level breakdown, general officer casualties, logistics collapse, centralization vs. decentralization tension
- Fires and precision-strike lessons: HIMARS effects, Russian counter-adaptations (dispersal, deception, camouflage revision)
- **Sources:** RUSI Stormbreak series; TRADOC G2 ATP 7-100.1; ISW; Jamestown; IISS; Carnegie
- **Deliverable:** 8–10 pp. — *"Tactical and Operational Doctrinal Evolution: Russia in Ukraine 2022–2025"*

## IV. Week 4 — Doctrinal Analysis: Strategic & Institutional
- Nuclear signaling: 2022–2024 rhetoric progression; Sep 2024 lowered-threshold language; ambiguity as coercion
- Mobilization doctrine: Sep 2022 partial mobilization — execution failures, societal tolerance limits, GOMU implications
- PMC/proxy forces post-Wagner: June 2023 mutiny; MoD absorption; current PMC doctrine
- Information warfare in wartime: Z/V narrative, Telegram milblogger ecosystem (Rybar) as General Staff feedback loop, information control limits
- Civil-military decision-making: Security Council role, GS autonomy, personalization of strategic decisions under wartime presidency
- **Deliverable:** 8–10 pp. — *"Strategic and Institutional Doctrinal Evolution: Russia in Ukraine 2022–2025"*

## V. Week 5 — Corpus Deep-Clean & Expansion
- Review all 30 entries: fix PDF extraction artifacts, flag pre-war assumptions needing Ukraine addenda, tighten broad entries, update keywords/topics
- Add 15–20 new entries:
  - Putin Feb 24 2022 SVO address
  - Sep 2024 nuclear deterrence policy update
  - VBpS establishment documents and Belousov statements
  - Ukraine tactical lessons (RUSI, TRADOC G2, ISW — open source only)
  - Wagner/PMC post-mutiny documents
  - Sep 2022 partial mobilization official statements
  - Russian National Security Strategy update
- Update `scripts/build_corpus.py` for reproducible regeneration; run loader test suite
- **Deliverable:** Expanded corpus (~45–50 entries); updated build script; *"Corpus Methodology"* paper section

## VI. Week 6 — Persona & Prompt Revision
- Add 11th shared cultural prior: *Wartime operational identity* — attrition as doctrine, moral authority of wartime sacrifice, gap between pre-war information-war-centric doctrine and conventional grinding reality
- Persona-specific updates (priority order):
  - VBpS: actual Ukraine drone employment patterns, formation experience, institutional standing contest
  - GRU: wartime intelligence failures, adaptations, milblogger ecosystem as informal input
  - GOMU: mobilization assumptions revised against Sep 2022 execution
  - CGS: operational art updated — maneuver-centric → fires-and-attrition
  - CINC: wartime personalization, reduced role of institutional staff process
- Review MODE 1/MODE 2 output formats against Week 2 test results; revise where pipeline produces generic outputs
- Document every change with rationale note (→ *"Persona Revision Methodology"* section)
- **Deliverable:** Revised persona files and cultural prior committed to repo; revision rationale document

## VII. Week 7 — Test Protocol Design
- Define evaluation dimensions: doctrinal grounding, anti-mirror-imaging, operational realism, institutional distinctiveness, wargame utility
- Write 6 scenario briefs (1–2 pp. each):
  1. Gray zone: Baltic state domestic unrest, Russian-speaking minority
  2. Cyber/info: significant offensive cyber op attributed to Russia
  3. Conventional escalation: NATO Art. 5, Suwalki Gap incident
  4. Nuclear signaling: adversary approaching stated Russian red line
  5. Strategic withdrawal: territorial concession with domestic political costs
  6. Coalition management: Chinese request for coordination on third-region objective
- Write evaluation rubric with scoring criteria per dimension
- Design blind review protocol for SME evaluation
- **Deliverable:** Test protocol; six scenario briefs; evaluation rubric

## VIII. Week 8 — Testing, External Review & Iteration
- Run all 6 scenarios × 3 WargameModes (FREEPLAY, PREDETERMINED, ANALYTIC)
- Score outputs against rubric; compile results matrix
- Send 2–3 de-identified outputs to SME reviewers for blind evaluation
- Identify top 3–5 systematic failure patterns; implement targeted fixes; re-run to confirm
- Document failure modes and fixes (→ *"Testing and Validation"* section)
- **Deliverable:** Test results matrix; iteration commits; SME feedback summary

## IX. Week 9 — Implications Analysis
- What LLMs can credibly model vs. cannot (intelligence inputs, classified params, personality, genuine surprise)
- The mirror-imaging problem: embedded Western assumptions in LLM training data; how ZARNITSA corrects for it; residual bias
- AI OPFOR vs. existing approaches: human roleplayers, rule-based systems, manual facilitator injection — when each is appropriate
- PME integration: facilitator training requirements, pre/post-exercise framing, what system is and is not designed to produce
- Ethics and distribution: open-source code + gated service model; educational adversary modeling vs. anonymous chatbot distinction
- Future research: real-time OSINT integration, multi-model debate architecture, embedding-based retrieval, human-factors evaluation with PME students
- **Deliverable:** 12–15 pp. implications and analysis section

## X. Week 10 — Integration & Final Deliverables
- Integrate all sections into complete paper; write abstract and executive summary
- Prepare 20–25 min briefing (format a military audience will actually consume)
- Repository polish: update README, fix pyproject.toml author field, tag `v0.1.0-practicum`
- Submit paper and briefing to advisor
- **Deliverable:** Complete research paper; presentation deck; final tagged repository

---

## Deliverables Summary

| Week | Output |
|------|--------|
| I | Annotated bibliography; research design statement |
| II | System audit memo |
| III | Doctrinal analysis — tactical/operational (8–10 pp.) |
| IV | Doctrinal analysis — strategic/institutional (8–10 pp.) |
| V | Expanded corpus (~45–50 entries); corpus methodology section |
| VI | Revised personas and cultural prior; revision rationale |
| VII | Test protocol; scenario briefs; evaluation rubric |
| VIII | Test results matrix; iteration commits; SME feedback |
| IX | AI implications analysis (12–15 pp.) |
| X | Complete paper; briefing deck; polished repository |

---

## Final Paper Structure

1. Abstract
2. Introduction and Research Questions
3. Background: AI in Wargaming and Adversary Simulation
4. System Description: ZARNITSA Architecture and Design
5. Doctrinal Analysis: Russian Military Doctrine Before and After Ukraine
   - 5.1 Tactical and Operational Evolution
   - 5.2 Strategic and Institutional Evolution
6. System Improvement: Corpus and Persona Revision Methodology
7. Testing and Validation: Protocol, Results, Limitations
8. Implications of AI-Based OPFOR Simulation
9. Conclusion
10. Bibliography
11. Appendices

---

## Key Open Sources

**Russian doctrine:** 2014 Military Doctrine; 2020/2024 Nuclear Deterrence Policy; Putin Feb 24 2022 address; Gerasimov 2013 VPK article

**Ukraine lessons-learned:** RUSI Stormbreak series; TRADOC G2 ATP 7-100.1; ISW analytical updates; Watling & Reynolds *"Meatgrinder"* (RUSI 2023)

**AI and wargaming:** Davis *"Toward Human-Machine Teaming in Wargaming"* (RAND 2023); Perla *The Art of Wargaming* (NIP 1990); Scharre *Army of None* (2018); *War on the Rocks*; *Modern War Institute*; *Journal of Defense Modeling and Simulation*
