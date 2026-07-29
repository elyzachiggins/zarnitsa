"""Persona-loader tests — verify the five council seats parse cleanly."""

from __future__ import annotations

from pathlib import Path

import pytest

from zarnitsa.exceptions import PersonaError
from zarnitsa.personas import load_persona, load_personas
from zarnitsa.types import PersonaRole

# The council was reduced from ten seats to five in 1cc9dc3/4543f8c; the archived
# personas live in data/personas/archived/ and are deliberately not loaded. This test
# previously still named the six removed roles as PersonaRole attributes, so it raised
# AttributeError at import and the whole file failed to collect.
EXPECTED_ROLES = {
    PersonaRole.GRU,
    PersonaRole.MOD,
    PersonaRole.CGS,
    PersonaRole.SOVBEZ,
    PersonaRole.CINC,
}


def test_all_five_personas_load() -> None:
    roles = {p.role for p in load_personas()}
    assert roles == EXPECTED_ROLES, f"missing or extra personas: {EXPECTED_ROLES ^ roles}"


def test_every_persona_role_is_reachable() -> None:
    """Every role in the enum must have a persona file, or the DAG silently skips it.

    _run_stage drops roles absent from the loaded dict, so a missing file produces a
    short deliberation rather than an error.
    """
    for role in PersonaRole:
        assert load_persona(role).role == role


def test_each_persona_has_system_prompt() -> None:
    for p in load_personas():
        assert p.system_prompt, f"{p.role} has empty system prompt"
        assert len(p.system_prompt) > 500, f"{p.role} system prompt is suspiciously short"


def test_each_persona_has_display_metadata() -> None:
    """The frontend renders russian_name and title; blank values ship blank cards."""
    for p in load_personas():
        assert p.russian_name.strip(), f"{p.role} has no russian_name"
        assert p.title.strip(), f"{p.role} has no title"


def test_load_persona_by_role() -> None:
    cgs = load_persona(PersonaRole.CGS)
    assert cgs.role == PersonaRole.CGS
    assert "General Staff" in cgs.title


def test_archived_personas_are_not_loaded() -> None:
    """archived/ is a subdirectory, so glob('*.md') must not reach into it."""
    assert len(load_personas()) == len(EXPECTED_ROLES)


def test_missing_directory_raises() -> None:
    with pytest.raises(PersonaError):
        load_personas(Path("does-not-exist"))


def test_returned_list_is_not_shared_state() -> None:
    """Callers get a fresh list; mutating it must not corrupt the cache."""
    first = load_personas()
    first.clear()
    assert len(load_personas()) == len(EXPECTED_ROLES)
