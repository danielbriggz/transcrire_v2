from nicegui import ui

from storage.db import get_connection
from storage.repositories.episodes_repo import EpisodesRepository
from storage.repositories.jobs_repo import JobsRepository
from storage.repositories.assets_repo import AssetsRepository
from core.pipeline import Pipeline
from domain.enums import Stage, AssetType
from interface.gui.tasks import run_stage_in_background, is_task_running
from interface.gui.websocket import setup_progress_ui
from app.logging import get_logger

logger = get_logger(__name__)

STAGE_LABELS = {
    Stage.FETCH:      "Fetch",
    Stage.TRANSCRIBE: "Transcribe",
    Stage.CAPTION:    "Generate Captions",
    Stage.IMAGE:      "Create Image",
}

ACTION_STAGE_MAP = {
    "fetch":             Stage.FETCH,
    "re_fetch":          Stage.FETCH,
    "transcribe":        Stage.TRANSCRIBE,
    "re_transcribe":     Stage.TRANSCRIBE,
    "generate_captions": Stage.CAPTION,
    "regenerate_caption":Stage.CAPTION,
    "create_image":      Stage.IMAGE,
    "regenerate_image":  Stage.IMAGE,
}


def _get_pipeline() -> Pipeline:
    conn = get_connection()
    return Pipeline(
        jobs_repo=JobsRepository(conn),
        episodes_repo=EpisodesRepository(conn),
        assets_repo=AssetsRepository(conn),
    )


@ui.page("/episode/new")
def new_episode_page() -> None:
    """Page for fetching a new episode from RSS."""
    with ui.column().classes("w-full max-w-2xl mx-auto p-6 gap-4"):
        ui.label("Fetch New Episode").classes("text-2xl font-bold")
        ui.separator()

        feed_input = ui.input(
            label="RSS Feed URL",
            placeholder="https://feeds.example.com/podcast.rss"
        ).classes("w-full")

        with ui.row().classes("gap-4 w-full"):
            episode_input = ui.number(label="Episode Number", value=1, min=1).classes("flex-1")
            season_input = ui.number(label="Season (optional)", value=None).classes("flex-1")

        status_label, progress_bar = setup_progress_ui("new")

        def on_fetch():
            feed_url = feed_input.value.strip()
            if not feed_url:
                ui.notify("Please enter a feed URL.", type="negative")
                return

            ui.notify("Fetching episode...", type="info")
            # Workers are implemented in Phase 5 worker layer (see note below)
            logger.info({
                "event": "fetch_requested",
                "feed_url": feed_url,
                "episode": episode_input.value,
                "season": season_input.value,
            })

        ui.button("Fetch Episode", on_click=on_fetch).props("color=primary").classes("w-full")
        ui.link("← Back to Dashboard", "/").classes("text-blue-500 text-sm")


@ui.page("/episode/{episode_id}")
def episode_page(episode_id: str) -> None:
    """Per-episode detail page with stage controls and output preview."""
    pipeline = _get_pipeline()
    episodes_repo = EpisodesRepository(get_connection())
    episode = episodes_repo.get_by_id(episode_id)

    if not episode:
        with ui.column().classes("p-8"):
            ui.label(f"Episode '{episode_id}' not found.").classes("text-red-500")
            ui.link("← Back to Dashboard", "/")
        return

    status = pipeline.get_status(episode_id)
    actions = status.available_actions

    with ui.column().classes("w-full max-w-3xl mx-auto p-6 gap-4"):

        # ── Header ────────────────────────────────────────────────────────────
        with ui.row().classes("w-full items-center gap-3"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat round")
            ui.label(episode.title).classes("text-2xl font-bold")

        ui.separator()

        # ── Stage progress tracker ────────────────────────────────────────────
        ui.label("Pipeline Progress").classes("text-lg font-semibold")
        with ui.row().classes("w-full gap-2 flex-wrap"):
            for stage in [Stage.FETCH, Stage.TRANSCRIBE, Stage.CAPTION, Stage.IMAGE]:
                completed = stage in status.completed_stages
                colour = "green" if completed else "grey"
                icon = "check_circle" if completed else "radio_button_unchecked"
                with ui.row().classes("items-center gap-1"):
                    ui.icon(icon, color=colour, size="sm")
                    ui.label(STAGE_LABELS[stage]).classes(
                        "text-sm font-medium text-green-600" if completed else "text-sm text-gray-400"
                    )

        # ── Live progress (WebSocket) ──────────────────────────────────────────
        if is_task_running(episode_id):
            ui.label("In Progress").classes("text-sm font-semibold text-blue-500 mt-2")
            setup_progress_ui(episode_id)

        ui.separator()

        # ── Available actions ─────────────────────────────────────────────────
        ui.label("Actions").classes("text-lg font-semibold")

        action_labels = {
            "fetch":              ("Fetch Episode",        "download"),
            "re_fetch":           ("Re-Fetch",             "refresh"),
            "transcribe":         ("Transcribe",           "record_voice_over"),
            "re_transcribe":      ("Re-Transcribe",        "refresh"),
            "generate_captions":  ("Generate Captions",    "edit_note"),
            "regenerate_caption": ("Regenerate Captions",  "refresh"),
            "create_image":       ("Create Quote Card",    "image"),
            "regenerate_image":   ("Regenerate Image",     "refresh"),
            "run_full_pipeline":  ("Run Full Pipeline",    "play_arrow"),
            "view_progress":      ("View Progress",        "sync"),
        }

        with ui.row().classes("gap-2 flex-wrap"):
            for action in actions:
                if action not in action_labels:
                    continue
                label, icon = action_labels[action]
                stage = ACTION_STAGE_MAP.get(action)

                def make_handler(a=action, s=stage):
                    def handle():
                        if s:
                            try:
                                job = pipeline.enqueue_stage(episode_id, s)
                                ui.notify(f"{STAGE_LABELS[s]} queued.", type="positive")
                                logger.info({"event": "action_triggered", "action": a, "job_id": job.id})
                            except ValueError as e:
                                ui.notify(str(e), type="negative")
                    return handle

                ui.button(label, icon=icon, on_click=make_handler()) \
                    .props("color=primary" if action in ("fetch", "transcribe", "generate_captions", "create_image", "run_full_pipeline") else "flat")

        ui.separator()

        # ── Output preview ────────────────────────────────────────────────────
        assets_repo = AssetsRepository(get_connection())

        transcript_asset = assets_repo.get_active(episode_id, AssetType.TRANSCRIPT)
        if transcript_asset:
            with ui.expansion("Transcript", icon="article").classes("w-full"):
                try:
                    from pathlib import Path
                    text = Path(transcript_asset.file_path).read_text(encoding="utf-8")
                    ui.textarea(value=text).classes("w-full font-mono text-sm") \
                        .props("readonly rows=10")
                except OSError:
                    ui.label("Transcript file not found on disk.").classes("text-red-400 text-sm")

        caption_asset = assets_repo.get_active(episode_id, AssetType.CAPTION)
        if caption_asset:
            with ui.expansion("Captions", icon="edit_note").classes("w-full"):
                try:
                    import json
                    from pathlib import Path
                    data = json.loads(Path(caption_asset.file_path).read_text(encoding="utf-8"))
                    for platform, caption_text in data.items():
                        if platform == "errors":
                            continue
                        ui.label(platform.capitalize()).classes("font-semibold text-sm mt-2")
                        ui.textarea(value=caption_text or "").classes("w-full text-sm") \
                            .props("readonly rows=4")
                except (OSError, json.JSONDecodeError):
                    ui.label("Caption file not found or unreadable.").classes("text-red-400 text-sm")

        image_asset = assets_repo.get_active(episode_id, AssetType.IMAGE)
        if image_asset:
            with ui.expansion("Quote Card", icon="image").classes("w-full"):
                from pathlib import Path
                if Path(image_asset.file_path).exists():
                    ui.image(image_asset.file_path).classes("max-w-sm rounded shadow")
                else:
                    ui.label("Image file not found on disk.").classes("text-red-400 text-sm")