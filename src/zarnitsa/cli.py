"""CLI entry point — `zarnitsa serve`, `zarnitsa list-personas`, etc."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from zarnitsa import __version__
from zarnitsa.config import settings

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
    """Diagnose configuration — check API keys, corpus, personas, provider reachability."""
    console.print(f"Backbone: [bold]{settings.backbone}[/bold]")
    console.print(f"Anthropic key set: {bool(settings.anthropic_api_key)}")
    console.print(f"Corpus snapshot: {settings.corpus_snapshot}")
    console.print(f"Fidelity mode: {settings.fidelity_mode}")


if __name__ == "__main__":
    app()
