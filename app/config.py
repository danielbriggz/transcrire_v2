from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict # type: ignore


class TranscrireConfig(BaseSettings): # type: ignore
    model_config = SettingsConfigDict( # type: ignore
        env_file=".env",
        env_prefix="TRANSCRIRE_",
        case_sensitive=False,
    )

    # API Keys (no prefix — set directly in .env)
    groq_api_key: str = ""
    gemini_api_key: str = ""

    # Paths (override via TRANSCRIRE_OUTPUT_DIR etc.)
    output_dir: Path = Path("output")
    assets_dir: Path = Path("assets")
    db_path: Path = Path("transcrire.db")
    config_dir: Path = Path.home() / ".transcrire"

    # Transcription defaults
    default_transcribe_mode: str = "CLOUD"
    default_transcript_type: str = "SEGMENT"


# Single shared instance — import this everywhere
config = TranscrireConfig()