"""Load persona markdown files from data/personas/ into Persona objects."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import frontmatter
from pydantic import BaseModel, Field

from zarnitsa.exceptions import PersonaError
from zarnitsa.types import PersonaRole

PERSONAS_DIR = Path(__file__).resolve().parents[3] / "data" / "personas"


class Persona(BaseModel):
    """An institutional council member."""

    role: PersonaRole
    russian_name: str
    title: str
    background: str = ""
    vocabulary_hints: list[str] = Field(default_factory=list)
    cites_tiers: list[str] = Field(default_factory=list)
    system_prompt: str


def _parse_file(path: Path) -> Persona:
    try:
        post = frontmatter.load(path)
    except Exception as e:
        raise PersonaError(f"failed to parse {path}: {e}") from e

    meta = post.metadata
    try:
        role = PersonaRole(meta["role"])
    except (KeyError, ValueError) as e:
        raise PersonaError(f"{path}: missing/invalid 'role' frontmatter") from e

    return Persona(
        role=role,
        russian_name=meta.get("russian_name", ""),
        title=meta.get("title", ""),
        background=meta.get("background", ""),
        vocabulary_hints=meta.get("vocabulary_hints", []),
        cites_tiers=meta.get("cites_tiers", []),
        system_prompt=post.content.strip(),
    )


@lru_cache(maxsize=1)
def load_personas(directory: Path | None = None) -> list[Persona]:
    base = directory or PERSONAS_DIR
    if not base.exists():
        raise PersonaError(f"persona directory not found: {base}")
    files = sorted(base.glob("*.md"))
    if not files:
        raise PersonaError(f"no persona files found in {base}")
    return [_parse_file(p) for p in files]


def load_persona(role: PersonaRole) -> Persona:
    for p in load_personas():
        if p.role == role:
            return p
    raise PersonaError(f"persona not defined for role: {role}")
