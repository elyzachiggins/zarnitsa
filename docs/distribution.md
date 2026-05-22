# Distribution

Zarnitsa has two distribution surfaces. They are deliberately decoupled.

## 1. Code — open source, MIT

- The repository (this one) is MIT-licensed.
- Anyone can read it, fork it, modify it, run it locally.
- The persona definitions, the orchestrator, the corpus pipeline, and the API server are all in the open.
- Code transparency is part of the educational value — researchers, analysts, and red-cell trainers can audit the institutional model, dispute persona drafts, and contribute corrections.

## 2. Deployed service — gated

The *hosted* Zarnitsa API is gated. The gate exists to limit the misuse vector where the system is consumed anonymously as a "Russian-perspective chatbot" by users who don't understand it is adversary modeling and not objective analysis.

Likely gate forms (TBD):
- Verified institutional email (`.mil`, `.gov`, accredited research institutions)
- Click-through acknowledgment of intended-use framing
- Per-deployment license issued to identified users
- Rate-limited free tier vs. unlimited identified tier

The gate is *not* security — anyone determined to stand up their own copy can. The gate is intended-use signaling, like the difference between a textbook on adversary tactics being publicly available and a course on adversary tactics being open enrollment.

## What this is *not*

- Not a defense secret — every persona is built from open-source doctrine, public speeches, and published analysis.
- Not a classified product — Zarnitsa cannot generate truthful classified-intelligence answers because it has no classified inputs.
- Not a propaganda tool — the cultural prior is for *modeling* Russian institutional thought, not advocating it. The system explicitly frames itself as adversary modeling.
- Not an analytical replacement — outputs should be treated as plausible adversary positions, not as factual claims about Russia.
