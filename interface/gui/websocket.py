from nicegui import ui, background_tasks
from events.emitter import emitter
from app.logging import get_logger

logger = get_logger(__name__)

# Per-client listeners registered on connect, removed on disconnect
_client_listeners: dict[str, list] = {}


def register_progress_listener(client_id: str, on_event_fn) -> None:
    """
    Register a callback for a specific browser client.
    Called when a client connects to a page that needs live updates.

    The callback receives a dict: {"event_type": str, "payload": dict}
    """
    def handler(payload: dict):
        try:
            on_event_fn(payload)
        except Exception as e:
            logger.warning({"event": "ws_callback_error", "client_id": client_id, "error": str(e)})

    events_to_watch = ["stage_started", "stage_completed", "stage_failed", "progress_update"]

    listeners = []
    for event_type in events_to_watch:
        def make_handler(et=event_type):
            def h(payload):
                handler({"event_type": et, "payload": payload})
            return h

        cb = make_handler()
        emitter.on(event_type, cb)
        listeners.append((event_type, cb))

    _client_listeners[client_id] = listeners
    logger.debug({"event": "ws_listener_registered", "client_id": client_id})


def unregister_progress_listener(client_id: str) -> None:
    """Remove all listeners for a disconnected client."""
    listeners = _client_listeners.pop(client_id, [])
    for event_type, cb in listeners:
        emitter.off(event_type, cb)
    logger.debug({"event": "ws_listener_removed", "client_id": client_id})


def setup_progress_ui(episode_id: str) -> tuple:
    """
    Create and return NiceGUI UI elements for live progress display.
    Registers listeners tied to the current client connection.

    Returns:
        (status_label, progress_bar) — NiceGUI elements the caller can place in layout.

    Usage in a page:
        status_label, progress_bar = setup_progress_ui(episode_id)
    """
    status_label = ui.label("Waiting...").classes("text-sm text-gray-500")
    progress_bar = ui.linear_progress(value=0).classes("w-full")
    progress_bar.visible = False

    client_id = str(id(status_label))

    def on_event(data: dict):
        event_type = data.get("event_type")
        payload = data.get("payload", {})

        if payload.get("episode_id") != episode_id:
            return  # Not our episode

        if event_type == "stage_started":
            stage = payload.get("stage", "")
            status_label.set_text(f"Running: {stage}...")
            progress_bar.visible = True
            progress_bar.value = 0

        elif event_type == "progress_update":
            pct = payload.get("percent", 0) / 100
            progress_bar.value = pct

        elif event_type == "stage_completed":
            stage = payload.get("stage", "")
            status_label.set_text(f"✓ {stage} complete")
            progress_bar.value = 1.0

        elif event_type == "stage_failed":
            error = payload.get("error", "Unknown error")
            status_label.set_text(f"✗ Failed: {error}").classes("text-red-500")
            progress_bar.visible = False

    register_progress_listener(client_id, on_event)
    ui.context.client.on_disconnect(lambda: unregister_progress_listener(client_id))

    return status_label, progress_bar