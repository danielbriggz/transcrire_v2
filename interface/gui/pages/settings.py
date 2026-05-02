import json
from pathlib import Path
from nicegui import ui

from app.config import config
from app.logging import get_logger

logger = get_logger(__name__)

CONFIG_PATH = Path.home() / ".transcrire" / "config.json"


def _load_saved_keys() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_keys(groq_key: str, gemini_key: str) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {"GROQ_API_KEY": groq_key, "GEMINI_API_KEY": gemini_key}
    CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    logger.info({"event": "api_keys_saved"})


@ui.page("/settings")
def settings_page() -> None:
    saved = _load_saved_keys()

    with ui.column().classes("w-full max-w-lg mx-auto p-8 gap-4"):
        ui.label("Settings").classes("text-2xl font-bold")
        ui.separator()

        ui.label("API Keys").classes("text-lg font-semibold mt-4")
        ui.label(
            "Keys are saved locally to ~/.transcrire/config.json and never uploaded."
        ).classes("text-sm text-gray-500")

        groq_input = ui.input(
            label="Groq API Key",
            value=saved.get("GROQ_API_KEY", ""),
            password=True,
            password_toggle_button=True,
        ).classes("w-full")

        gemini_input = ui.input(
            label="Gemini API Key",
            value=saved.get("GEMINI_API_KEY", ""),
            password=True,
            password_toggle_button=True,
        ).classes("w-full")

        def on_save():
            groq_val = groq_input.value.strip()
            gemini_val = gemini_input.value.strip()

            if not groq_val or not gemini_val:
                ui.notify("Both API keys are required.", type="negative")
                return

            _save_keys(groq_val, gemini_val)
            ui.notify("Keys saved. Restart Transcrire for them to take effect.", type="positive")
            logger.info({"event": "settings_saved"})

        ui.button("Save", on_click=on_save).classes("w-full mt-2")
        ui.separator()

        ui.label("Navigation").classes("text-sm text-gray-500")
        ui.link("← Back to Dashboard", "/").classes("text-blue-500")