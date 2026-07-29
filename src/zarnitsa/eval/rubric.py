"""Deterministic scoring for council output.

Every check here is mechanical — no LLM judge. That is a deliberate constraint: a
judged rubric costs money per evaluation, drifts as the judge model changes, and is
itself a thing you have to defend. These checks are reproducible, auditable, and free,
which makes them suitable as the selection evidence for "which backbone should
Zarnitsa use".

What they measure is *compliance*, not *quality*. A model can score 1.0 here and still
produce shallow analysis. Use these to eliminate models that fail the hard constraints
(refuses the task, ignores the language rules, doesn't ground in the corpus), then read
the surviving candidates' output by hand to choose between them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from zarnitsa.types import PersonaTurn

# Cyrillic abbreviations the language rule requires be transliterated to Latin.
_BANNED_CYRILLIC_ABBR = [
    "ГРУ", "МО", "НГШ", "ВГК", "Совбез", "ГШ", "ГОУ", "ГОМУ", "НЦУО", "ЦВСИ",
    "РЭБ", "ВКС", "ВМФ", "ВДВ", "МВД", "ФСБ", "СВР", "ФСО", "ОГВ", "ОПК",
    "Росгвардия", "ДНР", "ЛНР",
]

# A markdown heading whose first word-character is Cyrillic violates "English first".
_CYRILLIC_HEADING = re.compile(r"^#{1,6}\s+[^\w\n]*[Ѐ-ӿ]", re.MULTILINE)

# A standalone Cyrillic salutation, rather than "Comrades."
_CYRILLIC_SALUTATION = re.compile(r"^\s*(Товарищи|Господа)\b", re.MULTILINE)

# Signals the model broke frame and spoke as an assistant rather than as the persona.
_BREAK_FRAME = [
    "as an ai", "as a language model", "i cannot", "i can't help",
    "i'm not able to", "i am not able to", "i must decline", "i won't",
    "it's important to note that this is a simulation",
    "i should clarify that i", "this is a fictional",
    "i do not have the ability", "i'm unable to",
]

# Latin-script transliterations that should be present if the rule is being followed.
_EXPECTED_TRANSLIT = ["GRU", "NGSh", "VGK", "Sovbez", "MO", "GSh"]


@dataclass
class TurnScore:
    persona: str
    chars: int
    cited: bool
    citation_count: int
    cyrillic_headings: int
    banned_abbr: list[str] = field(default_factory=list)
    cyrillic_salutation: bool = False
    broke_frame: list[str] = field(default_factory=list)
    empty: bool = False

    @property
    def language_ok(self) -> bool:
        return (
            self.cyrillic_headings == 0
            and not self.banned_abbr
            and not self.cyrillic_salutation
        )

    @property
    def in_frame(self) -> bool:
        return not self.broke_frame


def score_turn(turn: PersonaTurn) -> TurnScore:
    text = turn.content or ""
    lower = text.lower()
    return TurnScore(
        persona=turn.persona.value,
        chars=len(text),
        cited=bool(turn.citations),
        citation_count=len(turn.citations),
        cyrillic_headings=len(_CYRILLIC_HEADING.findall(text)),
        banned_abbr=sorted({a for a in _BANNED_CYRILLIC_ABBR if a in text}),
        cyrillic_salutation=bool(_CYRILLIC_SALUTATION.search(text)),
        broke_frame=[p for p in _BREAK_FRAME if p in lower],
        empty=not text.strip(),
    )


@dataclass
class RunScore:
    """Aggregate across all turns of one deliberation."""

    scenario: str
    turns: list[TurnScore]
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float | None = None
    seconds: float = 0.0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.turns)

    @property
    def citation_rate(self) -> float:
        """Fraction of turns that cited at least one corpus entry."""
        return _mean([t.cited for t in self.turns])

    @property
    def language_compliance(self) -> float:
        return _mean([t.language_ok for t in self.turns])

    @property
    def in_frame_rate(self) -> float:
        """Fraction of turns that stayed in persona rather than breaking to assistant voice."""
        return _mean([t.in_frame for t in self.turns])

    @property
    def transliteration_used(self) -> bool:
        joined = " ".join(t.persona for t in self.turns)
        return bool(joined)

    @property
    def mean_chars(self) -> float:
        return _mean([float(t.chars) for t in self.turns])

    @property
    def violations(self) -> list[str]:
        out: list[str] = []
        for t in self.turns:
            if t.empty:
                out.append(f"{t.persona}: empty output")
            if t.banned_abbr:
                out.append(f"{t.persona}: Cyrillic abbr {', '.join(t.banned_abbr)}")
            if t.cyrillic_headings:
                out.append(f"{t.persona}: {t.cyrillic_headings} Cyrillic heading(s)")
            if t.cyrillic_salutation:
                out.append(f"{t.persona}: Cyrillic salutation")
            if t.broke_frame:
                out.append(f"{t.persona}: broke frame ({t.broke_frame[0]!r})")
        return out


def _mean(values: list[bool] | list[float]) -> float:
    if not values:
        return 0.0
    return sum(float(v) for v in values) / len(values)


@dataclass
class ModelReport:
    label: str
    runs: list[RunScore]

    @property
    def completed(self) -> list[RunScore]:
        return [r for r in self.runs if r.ok]

    @property
    def failure_count(self) -> int:
        return len(self.runs) - len(self.completed)

    def _avg(self, attr: str) -> float:
        vals = [getattr(r, attr) for r in self.completed]
        return sum(vals) / len(vals) if vals else 0.0

    @property
    def citation_rate(self) -> float:
        return self._avg("citation_rate")

    @property
    def language_compliance(self) -> float:
        return self._avg("language_compliance")

    @property
    def in_frame_rate(self) -> float:
        return self._avg("in_frame_rate")

    @property
    def mean_chars(self) -> float:
        return self._avg("mean_chars")

    @property
    def mean_seconds(self) -> float:
        return self._avg("seconds")

    @property
    def total_cost(self) -> float | None:
        costs = [r.cost_usd for r in self.completed if r.cost_usd is not None]
        return sum(costs) if costs else None

    @property
    def total_tokens(self) -> tuple[int, int]:
        return (
            sum(r.input_tokens for r in self.completed),
            sum(r.output_tokens for r in self.completed),
        )
