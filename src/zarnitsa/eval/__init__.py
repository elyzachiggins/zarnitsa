"""Model evaluation — deterministic scoring of council output across backbones."""

from zarnitsa.eval.rubric import ModelReport, RunScore, TurnScore, score_turn
from zarnitsa.eval.runner import evaluate, load_scenarios, parse_model_spec, to_json

__all__ = [
    "ModelReport",
    "RunScore",
    "TurnScore",
    "evaluate",
    "load_scenarios",
    "parse_model_spec",
    "score_turn",
    "to_json",
]
