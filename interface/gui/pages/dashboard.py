from nicegui import ui

from storage.db import get_connection
from storage.repositories.episodes_repo import EpisodesRepository
from storage.repositories.jobs_repo import JobsRepository
from storage.repositories.assets_repo import AssetsRepository
from core.pipeline import Pipeline
from app.logging import get_logger

logger = get_logger(__name__)

# Status badge colours
STATUS_COLOURS = {
    0: "grey",
    1: "blue",
    2: "blue",
    3: "blue",
    4: "green",
}


def _get_pipeline() -> Pipeline:
    conn = get_connection()
    return Pipeline(
        jobs_repo=JobsRepository(conn),
        episodes_repo=EpisodesRepository(conn),
        assets_repo=AssetsRepository(conn),
    )


def _status_label(completion_level: int) -> str:
    labels = {
        0: "New",
        1: "Fetched",
        2: "Transcribed",
        3: "Captioned",
        4: "Complete",
    }
    return labels.get(completion_level, "Unknown")


@ui.page("/")
def dashboard_page() -> None:
    pipeline = _get_pipeline()
    episodes_repo = EpisodesRepository(get_connection())
    episodes = episodes_repo.list_all()

    with ui.column().classes("w-full max-w-4xl mx-auto p-6 gap-4"):

        # ── Header ───────────────────────────────────────────────────────────
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("Transcrire").classes("text-3xl font-bold")
            with ui.row().classes("gap-2"):
                ui.button("Settings", on_click=lambda: ui.navigate.to("/settings")) \
                    .props("flat")
                ui.button(
                    "New Episode",
                    on_click=lambda: ui.navigate.to("/episode/new")
                ).props("color=primary")

        ui.separator()

        # ── Episode list ──────────────────────────────────────────────────────
        if not episodes:
            with ui.column().classes("w-full items-center py-16 gap-2"):
                ui.icon("podcasts", size="4rem").classes("text-gray-300")
                ui.label("No episodes yet.").classes("text-gray-400 text-lg")
                ui.label("Add your RSS feed URL to get started.").classes("text-gray-400 text-sm")
                ui.button(
                    "Fetch First Episode",
                    on_click=lambda: ui.navigate.to("/episode/new")
                ).props("color=primary")
        else:
            for episode in episodes:
                status = pipeline.get_status(episode.id)
                _render_episode_card(episode, status)


def _render_episode_card(episode, status) -> None:
    """Render a single episode card with status badge and action buttons."""
    colour = STATUS_COLOURS.get(status.completion_level, "grey")
    label = _status_label(status.completion_level)

    with ui.card().classes("w-full"):
        with ui.row().classes("w-full items-center justify-between"):

            # Episode info
            with ui.column().classes("gap-1"):
                ui.label(episode.title).classes("font-semibold text-base")
                if episode.published_date:
                    ui.label(episode.published_date).classes("text-sm text-gray-400")

            # Status badge + action button
            with ui.row().classes("items-center gap-3"):
                ui.badge(label, color=colour)

                if status.active_job:
                    ui.button("View Progress", icon="sync") \
                        .props("flat size=sm") \
                        .on_click(lambda e=episode: ui.navigate.to(f"/episode/{e.id}"))
                else:
                    ui.button("Open", icon="arrow_forward") \
                        .props("flat size=sm") \
                        .on_click(lambda e=episode: ui.navigate.to(f"/episode/{e.id}"))