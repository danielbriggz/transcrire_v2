import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from storage.files import write_text_atomic
from app.config import config
from app.logging import get_logger

logger = get_logger(__name__)

MANIFEST_FILENAME = "manifest.json"


def _manifest_path(episode_id: str) -> Path:
    return config.output_dir / episode_id / MANIFEST_FILENAME


def write_manifest(episode_id: str, data: dict) -> Path:
    """
    Write or overwrite the episode manifest sidecar.

    The manifest should contain enough to reconstruct the episode
    record in the DB if needed. At minimum:
        {
            "episode_id": "...",
            "title": "...",
            "feed_url": "...",
            "stages_completed": ["FETCH", "TRANSCRIBE"],
            "assets": {
                "audio": {"path": "...", "checksum": "..."},
                "transcript": {"path": "...", "checksum": "..."}
            },
            "last_updated": "2024-01-01T12:00:00Z"
        }
    """
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    data["episode_id"] = episode_id

    path = _manifest_path(episode_id)
    write_text_atomic(path, json.dumps(data, indent=2))
    logger.info({"event": "manifest_written", "episode_id": episode_id, "path": str(path)})
    return path


def load_manifest(episode_id: str) -> Optional[dict]:
    """
    Load and parse the manifest for an episode.
    Returns None if no manifest exists.
    """
    path = _manifest_path(episode_id)
    if not path.exists():
        logger.debug({"event": "manifest_not_found", "episode_id": episode_id})
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.error({"event": "manifest_read_failed", "episode_id": episode_id, "error": str(e)})
        return None


def manifest_exists(episode_id: str) -> bool:
    return _manifest_path(episode_id).exists()


def update_manifest_field(episode_id: str, key: str, value) -> None:
    """
    Convenience method to update a single field without rewriting the whole manifest.
    Loads existing manifest, updates field, writes back atomically.
    """
    existing = load_manifest(episode_id) or {}
    existing[key] = value
    write_manifest(episode_id, existing)