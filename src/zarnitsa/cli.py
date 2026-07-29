"""CLI entry point — `zarnitsa serve`, `zarnitsa list-personas`, etc."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from zarnitsa import __version__
from zarnitsa.config import settings
from zarnitsa.types import PersonaRole

app = typer.Typer(
    name="zarnitsa",
    help="Institutional Russian decision-modeling council.",
    add_completion=False,
    no_args_is_help=True,
)
console = Console()


@app.command()
def version() -> None:
    """Print Zarnitsa version."""
    console.print(f"zarnitsa [bold cyan]{__version__}[/bold cyan]")


@app.command()
def serve(
    host: str = typer.Option(None, help="Override bind host."),
    port: int = typer.Option(None, help="Override bind port."),
) -> None:
    """Start the FastAPI server."""
    import uvicorn

    uvicorn.run(
        "zarnitsa.api.app:app",
        host=host or settings.host,
        port=port or settings.port,
        reload=False,
    )


@app.command("list-personas")
def list_personas() -> None:
    """List the personas defined in data/personas/."""
    from zarnitsa.personas.loader import load_personas

    personas = load_personas()
    table = Table(title="Council personas")
    table.add_column("Role", style="cyan")
    table.add_column("Russian", style="magenta")
    table.add_column("Title")
    for p in personas:
        table.add_row(p.role.value, p.russian_name, p.title)
    console.print(table)


@app.command()
def doctor() -> None:
    """Diagnose configuration — keys, corpus integrity, personas, security posture.

    The corpus check actually loads and indexes every entry rather than reporting the
    configured snapshot name. A malformed frontmatter block in a single file takes the
    whole corpus offline, and because the orchestrator catches retrieval errors and
    continues, that failure is otherwise invisible from the outside.
    """
    ok = True

    console.print("[bold]Backbone[/bold]")
    console.print(f"  supporting personas : {settings.backbone}")
    cinc_backbone, cinc_model = settings.backbone_for(is_cinc=True)
    console.print(f"  CINC                : {cinc_backbone} ({cinc_model or 'default model'})")
    console.print(f"  prompt cache        : {'on' if settings.prompt_cache else 'off'}")

    console.print("\n[bold]Credentials[/bold]")
    for label, value in (
        ("ANTHROPIC_API_KEY", settings.anthropic_api_key),
        ("OPENROUTER_API_KEY", settings.openrouter_api_key),
    ):
        console.print(f"  {label:<20} {'[green]set[/green]' if value else '[dim]unset[/dim]'}")

    console.print("\n[bold]Corpus[/bold]")
    console.print(f"  data dir            : {settings.resolved_data_dir}")
    console.print(f"  snapshot            : {settings.corpus_snapshot}")
    try:
        from zarnitsa.corpus import Retriever

        retriever = Retriever()
        console.print(f"  entries indexed     : [green]{len(retriever)}[/green]")
        probe = retriever.search("nuclear deterrence", top_k=1)
        if probe:
            console.print(f"  retrieval probe     : [green]ok[/green] -> {probe[0][0].id}")
        else:
            console.print("  retrieval probe     : [yellow]no hits[/yellow]")
            ok = False
    except Exception as e:
        console.print(f"  [red]CORPUS FAILED TO LOAD:[/red] {e}")
        console.print("  [yellow]Deliberations will run with NO grounding.[/yellow]")
        ok = False

    console.print("\n[bold]Personas[/bold]")
    try:
        from zarnitsa.personas import load_personas

        personas = load_personas()
        console.print(f"  loaded              : [green]{len(personas)}[/green]")
        missing = [r.value for r in PersonaRole if r not in {p.role for p in personas}]
        if missing:
            console.print(f"  [red]missing seats:[/red] {', '.join(missing)}")
            ok = False
    except Exception as e:
        console.print(f"  [red]PERSONAS FAILED TO LOAD:[/red] {e}")
        ok = False

    console.print("\n[bold]Security[/bold]")
    if settings.auth_required:
        console.print(f"  API keys configured : [green]{len(settings.api_key_set)}[/green]")
    else:
        console.print("  API keys configured : [red]none — council endpoints are PUBLIC[/red]")
        if settings.cors_origins == ["*"]:
            console.print("  [red]CORS is '*' with no auth: anyone can spend your model budget.[/red]")
        ok = False
    console.print(
        f"  rate limit          : {settings.rate_limit_requests} "
        f"per {settings.rate_limit_window_seconds}s"
        + ("  [yellow](disabled)[/yellow]" if settings.rate_limit_requests <= 0 else "")
    )

    console.print()
    if ok:
        console.print("[bold green]All checks passed.[/bold green]")
    else:
        console.print("[bold yellow]Some checks failed — see above.[/bold yellow]")
        raise typer.Exit(code=1)


@app.command("eval")
def eval_models(
    models: list[str] = typer.Option(
        None,
        "--models",
        "-m",
        help="backbone:model, repeatable. e.g. openrouter:deepseek/deepseek-v3.2",
    ),
    scenarios: Path = typer.Option(None, help="Scenario YAML (default data/eval/scenarios.yaml)."),
    out: Path = typer.Option(None, help="Write full JSON results here."),
    concurrency: int = typer.Option(2, help="Scenarios in flight per model."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the cost confirmation."),
) -> None:
    """Score backbones against the fixed scenario set. Spends real money."""
    import asyncio

    from zarnitsa.eval import evaluate, load_scenarios, to_json

    specs = models or [f"{settings.backbone}:{settings.anthropic_model}"]
    cases = load_scenarios(scenarios)

    calls = len(specs) * len(cases) * 5
    console.print(
        f"[bold]{len(specs)} model(s) x {len(cases)} scenario(s) x 5 seats "
        f"= {calls} completions[/bold]"
    )
    if not yes and not typer.confirm("This spends real money. Continue?"):
        raise typer.Abort()

    def progress(spec: str, run) -> None:
        status = "[red]FAIL[/red]" if run.error else "[green]ok[/green]"
        console.print(f"  {status} {spec} :: {run.scenario} ({run.seconds:.1f}s)")

    reports = asyncio.run(evaluate(specs, cases, concurrency=concurrency, on_progress=progress))

    table = Table(title="Backbone comparison")
    table.add_column("Model", style="cyan", no_wrap=True)
    table.add_column("Fail", justify="right")
    table.add_column("Cited", justify="right")
    table.add_column("Lang", justify="right")
    table.add_column("InFrame", justify="right")
    table.add_column("Chars", justify="right")
    table.add_column("Sec", justify="right")
    table.add_column("Cost $", justify="right")
    for r in reports:
        cost = f"{r.total_cost:.4f}" if r.total_cost is not None else "—"
        table.add_row(
            r.label,
            str(r.failure_count),
            f"{r.citation_rate:.0%}",
            f"{r.language_compliance:.0%}",
            f"{r.in_frame_rate:.0%}",
            f"{r.mean_chars:.0f}",
            f"{r.mean_seconds:.1f}",
            cost,
        )
    console.print(table)

    for r in reports:
        violations = [v for run in r.completed for v in run.violations]
        if violations:
            console.print(f"\n[yellow]{r.label} violations:[/yellow]")
            for v in violations[:12]:
                console.print(f"  - {v}")
        for run in r.runs:
            if run.error:
                console.print(f"\n[red]{r.label} error on {run.scenario}:[/red] {run.error}")

    if out:
        out.write_text(to_json(reports), encoding="utf-8")
        console.print(f"\nFull results written to [bold]{out}[/bold]")


if __name__ == "__main__":
    app()
