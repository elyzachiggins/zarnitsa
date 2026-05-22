"""Persona-loader smoke tests — verify the 10 council members parse cleanly."""

from __future__ import annotations

from zarnitsa.personas import load_persona, load_personas
from zarnitsa.types import PersonaRole


def test_all_ten_personas_load() -> None:
    personas = load_personas()
    roles = {p.role for p in personas}
    expected = {
        PersonaRole.CGS,
        PersonaRole.GOU,
        PersonaRole.GOMU,
        PersonaRole.TSVSI,
        PersonaRole.GRU,
        PersonaRole.VBPS,
        PersonaRole.MOD,
        PersonaRole.CINC,
        PersonaRole.SINO_LIAISON,
        PersonaRole.ECON_ADVISOR,
    }
    assert roles == expected, f"missing or extra personas: {expected ^ roles}"


def test_each_persona_has_system_prompt() -> None:
    for p in load_personas():
        assert p.system_prompt, f"{p.role} has empty system prompt"
        assert len(p.system_prompt) > 500, f"{p.role} system prompt is suspiciously short"


def test_load_persona_by_role() -> None:
    cgs = load_persona(PersonaRole.CGS)
    assert cgs.role == PersonaRole.CGS
    assert "General Staff" in cgs.title
