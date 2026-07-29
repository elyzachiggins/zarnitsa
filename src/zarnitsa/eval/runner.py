"""Run the council across scenarios and backbones, and score the output.

Usage (from the repo root):

    zarnitsa eval --models openrouter:deepseek/deepseek-v3.2 \
                  --models openrouter:moonshotai/kimi-k2-thinking \
                  --models anthropic:claude-opus-4-7

Each --models value is `backbone:model`. Every model runs every scenario, so results
are directly comparable. Output is a table plus a JSON dump for the writeup.

Cost warning: this spends real money. Five model calls per scenario per model. With
5 scenarios and 3 models that is 75 completions.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict
from pathlib import Path

import yaml

from zarnitsa.config import settings
from zarnitsa.eval.rubric import ModelReport, RunScore, score_turn
from zarnitsa.orchestrator.graph import run_council
from zarnitsa.providers.factory import get_provider
from zarnitsa.types import CouncilRequest, WargameMode

DEFAULT_SCENARIOS = Path("data/eval/scenarios.yaml")


def load_scenarios(path: Path | None = None) -> list[dict[str, str]]:
    src = path or DEFAULT_SCENARIOS
    if not src.exists():
        raise FileNotFoundError(f"scenario file not found: {src}")
    data = yaml.safe_load(src.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ValueError(f"{src}: expected a list of scenarios")
    return data


def parse_model_spec(spec: str) -> tuple[str, str | None]:
    """`backbone:model` -> (backbone, model). A bare backbone uses its configured default."""
    if ":" not in spec:
        return spec, None
    backbone, model = spec.split(":", 1)
    return backbone, model or None


async def run_one(
    scenario: dict[str, str],
    backbone: str,
    model: str | None,
) -> RunScore:
    provider = get_provider(backbone, model)  # type: ignore[arg-type]
    request = CouncilRequest(
        scenario=scenario["scenario"],
        wargame_mode=WargameMode(scenario.get("mode", "strategic")),
        cinc_intent=scenario.get("cinc_intent"),
    )
    started = time.monotonic()
    try:
        response = await run_council(request, provider=provider)
    except Exception as e:
        return RunScore(
            scenario=scenario.get("name", scenario["scenario"][:40]),
            turns=[],
            seconds=time.monotonic() - started,
            error=f"{type(e).__name__}: {e}",
        )

    usage = response.metadata.get("usage", {})
    return RunScore(
        scenario=scenario.get("name", scenario["scenario"][:40]),
        turns=[score_turn(t) for t in response.turns],
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        cache_read_tokens=usage.get("cache_read_tokens", 0),
        cost_usd=usage.get("cost_usd"),
        seconds=time.monotonic() - started,
    )


async def evaluate(
    specs: list[str],
    scenarios: list[dict[str, str]],
    *,
    concurrency: int = 2,
    on_progress=None,
) -> list[ModelReport]:
    async def run_model(spec: str) -> ModelReport:
        """One model against every scenario.

        Kept as a function rather than a closure over the loop variable: binding
        `spec` and `semaphore` per call is what makes this safe to later run models
        concurrently instead of sequentially.
        """
        backbone, model = parse_model_spec(spec)
        semaphore = asyncio.Semaphore(concurrency)

        async def guarded(scenario: dict[str, str]) -> RunScore:
            async with semaphore:
                result = await run_one(scenario, backbone, model)
                if on_progress:
                    on_progress(spec, result)
                return result

        runs = await asyncio.gather(*(guarded(s) for s in scenarios))
        return ModelReport(label=spec, runs=list(runs))

    # Sequential across models on purpose: running them in parallel would interleave
    # latency measurements and make `mean_seconds` meaningless as a comparison.
    return [await run_model(spec) for spec in specs]


def to_json(reports: list[ModelReport]) -> str:
    payload = [
        {
            "model": r.label,
            "snapshot": settings.corpus_snapshot,
            "failures": r.failure_count,
            "citation_rate": round(r.citation_rate, 4),
            "language_compliance": round(r.language_compliance, 4),
            "in_frame_rate": round(r.in_frame_rate, 4),
            "mean_chars": round(r.mean_chars, 1),
            "mean_seconds": round(r.mean_seconds, 2),
            "total_cost_usd": r.total_cost,
            "input_tokens": r.total_tokens[0],
            "output_tokens": r.total_tokens[1],
            "runs": [
                {
                    **{
                        k: v
                        for k, v in asdict(run).items()
                        if k not in {"turns"}
                    },
                    "violations": run.violations,
                    "turns": [asdict(t) for t in run.turns],
                }
                for run in r.runs
            ],
        }
        for r in reports
    ]
    return json.dumps(payload, indent=2, ensure_ascii=False)
