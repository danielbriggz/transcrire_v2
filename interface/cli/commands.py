import typer
from rich.console import Console
from rich.table import Table

from storage.db import get_connection, run_migrations
from storage.repositories.episodes_repo import EpisodesRepository
from storage.repositories.jobs_repo import JobsRepository
from storage.repositories.assets_repo import AssetsRepository
from core.pipeline import Pipeline
from domain.enums import Stage

app = typer.Typer(help="Episode management commands.")
console = Console()


def _get_pipeline() -> Pipeline:
    conn = get_connection()
    run_migrations(conn)
    return Pipeline(
        jobs_repo=JobsRepository(conn),
        episodes_repo=EpisodesRepository(conn),
        assets_repo=AssetsRepository(conn),
    )


@app.command()
def list():
    """List all episodes and their current pipeline status."""
    episodes_repo = EpisodesRepository(get_connection())
    pipeline = _get_pipeline()
    episodes = episodes_repo.list_all()

    if not episodes:
        console.print("[yellow]No episodes found.[/yellow]")
        raise typer.Exit()

    table = Table(title="Episodes")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Title")
    table.add_column("Status")
    table.add_column("Completion")

    for ep in episodes:
        status = pipeline.get_status(ep.id)
        completion = f"{status.completion_level}/4"
        table.add_row(ep.id[:8], ep.title, str(status.completion_level), completion)

    console.print(table)


@app.command()
def run(
    episode_id: str = typer.Argument(..., help="Episode ID to process."),
    stage: str = typer.Option(None, "--stage", "-s", help="Run a specific stage only."),
    full: bool = typer.Option(False, "--full", "-f", help="Run all stages unattended."),
):
    """
    Run pipeline stages for an episode.

    Examples:
        transcrire episode run <id> --full
        transcrire episode run <id> --stage TRANSCRIBE
    """
    pipeline = _get_pipeline()

    if full:
        jobs = pipeline.enqueue_full(episode_id)
        console.print(f"[green]Queued {len(jobs)} stages for episode {episode_id}.[/green]")
        return

    if stage:
        try:
            stage_enum = Stage[stage.upper()]
        except KeyError:
            console.print(f"[red]Unknown stage: {stage}. Valid stages: {[s.name for s in Stage]}[/red]")
            raise typer.Exit(1)

        try:
            job = pipeline.enqueue_stage(episode_id, stage_enum)
            console.print(f"[green]Queued {stage_enum.value} — job ID: {job.id}[/green]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)
        return

    # No flags — show available actions
    status = pipeline.get_status(episode_id)
    console.print(f"\nEpisode: [bold]{episode_id}[/bold]")
    console.print(f"Completion: {status.completion_level}/4")
    console.print(f"Available actions: {status.available_actions}")


@app.command()
def status(episode_id: str = typer.Argument(..., help="Episode ID to inspect.")):
    """Show detailed pipeline status for an episode."""
    pipeline = _get_pipeline()
    s = pipeline.get_status(episode_id)

    console.print(f"\n[bold]Episode:[/bold] {episode_id}")
    console.print(f"[bold]Completion:[/bold] {s.completion_level}/4")
    console.print(f"[bold]Completed stages:[/bold] {[st.value for st in s.completed_stages]}")
    console.print(f"[bold]Pending stages:[/bold] {[st.value for st in s.pending_stages]}")
    console.print(f"[bold]Active job:[/bold] {s.active_job.id if s.active_job else 'None'}")
    console.print(f"[bold]Available actions:[/bold] {s.available_actions}")