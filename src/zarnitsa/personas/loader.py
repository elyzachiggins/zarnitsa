"""Load persona markdown files from data/personas/ into Persona objects."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import frontmatter
from pydantic import BaseModel, Field

from zarnitsa.config import settings
from zarnitsa.exceptions import PersonaError
from zarnitsa.types import PersonaRole


def personas_dir() -> Path:
    """Resolve the persona directory through the same setting the corpus uses.

    This was previously a module-level `Path(__file__).parents[3] / "data" / "personas"`,
    which walks out of site-packages on a non-editable install and ignores
    ZARNITSA_DATA_DIR entirely — so the corpus and the personas could disagree about
    where `data/` is.
    """
    return settings.resolved_data_dir / "personas"


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


@lru_cache(maxsize=4)
def _load_personas_cached(base: Path) -> tuple[Persona, ...]:
    if not base.exists():
        raise PersonaError(f"persona directory not found: {base}")
    files = sorted(base.glob("*.md"))
    if not files:
        raise PersonaError(f"no persona files found in {base}")
    personas = []
    for p in files:
        post = frontmatter.load(p)
        if "role" not in post.metadata:
            continue  # skip README.md and other non-persona markdown
        personas.append(_parse_file(p))
    if not personas:
        raise PersonaError(f"no files with a 'role' frontmatter key in {base}")
    return tuple(personas)


def load_personas(directory: Path | None = None) -> list[Persona]:
    """Load the council personas. Cached per directory.

    Returns a fresh list each call: the cache holds a tuple, so a caller that mutates
    the result can't corrupt what every later caller sees.
    """
    return list(_load_personas_cached(directory or personas_dir()))


def load_persona(role: PersonaRole) -> Persona:
    for p in load_personas():
        if p.role == role:
            return p
    raise PersonaError(f"persona not defined for role: {role}")
