from nicegui import ui, app as nicegui_app

from app.lifecycle import startup, shutdown
from interface.gui.pages import dashboard, settings, episode
from app.logging import get_logger

logger = get_logger(__name__)


def create_app() -> None:
    """Register all pages and lifecycle hooks with NiceGUI."""

    nicegui_app.on_startup(startup)
    nicegui_app.on_shutdown(shutdown)

    # Pages are registered by importing their modules.
    # Each page module calls @ui.page('/path') at module level.
    # Importing them here is sufficient to register them.
    _ = dashboard
    _ = settings
    _ = episode


def run() -> None:
    """Start the NiceGUI server."""
    create_app()
    ui.run(
        host="127.0.0.1",
        port=7860,
        title="Transcrire",
        reload=False,
        show=True,          # Opens browser tab automatically on start
    )


if __name__ in {"__main__", "__mp_main__"}:
    run()