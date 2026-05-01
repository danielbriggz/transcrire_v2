import hashlib
import shutil
from pathlib import Path

from app.logging import get_logger

logger = get_logger(__name__)

CHUNK_SIZE = 65536  # 64KB chunks for checksum calculation


def compute_checksum(file_path: Path) -> str:
    """
    Compute the SHA-256 hash of a file.
    Returns hex digest string.
    Reads in chunks to handle large audio files without memory issues.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            sha256.update(chunk)
    return sha256.hexdigest()


def write_file_atomic(destination: Path, content: bytes) -> None:
    """
    Write content to a file atomically using a temp-then-rename pattern.

    Why atomic? If the process crashes mid-write, the destination file
    remains intact (either the old version or the new version — never partial).
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_suffix(destination.suffix + ".tmp")

    try:
        tmp_path.write_bytes(content)
        tmp_path.replace(destination)  # Atomic on same filesystem
        logger.debug({"event": "file_written", "path": str(destination)})
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        logger.error({"event": "file_write_failed", "path": str(destination), "error": str(e)})
        raise


def write_text_atomic(destination: Path, content: str, encoding: str = "utf-8") -> None:
    """Convenience wrapper for writing text files atomically."""
    write_file_atomic(destination, content.encode(encoding))


def ensure_episode_folder(base_output_dir: Path, episode_id: str) -> Path:
    """
    Create and return the output folder for a specific episode.
    Structure: <output_dir>/<episode_id>/
    """
    folder = base_output_dir / episode_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def safe_delete(file_path: Path) -> bool:
    """
    Delete a file if it exists. Returns True if deleted, False if not found.
    Never raises on missing files.
    """
    try:
        file_path.unlink(missing_ok=True)
        logger.debug({"event": "file_deleted", "path": str(file_path)})
        return True
    except Exception as e:
        logger.warning({"event": "file_delete_failed", "path": str(file_path), "error": str(e)})
        return False


def copy_file(source: Path, destination: Path) -> None:
    """Copy a file, creating parent directories as needed."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    logger.debug({"event": "file_copied", "from": str(source), "to": str(destination)})