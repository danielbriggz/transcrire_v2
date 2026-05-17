import subprocess
import json
import sys
import os
from pathlib import Path
from typing import Optional

from utils.retry import AudioProcessingError
from app.logging import get_logger

logger = get_logger(__name__)

GROQ_MAX_BYTES = 25 * 1024 * 1024   # 25 MB — Groq's per-request file size limit
CHUNK_DURATION_SECONDS = 600         # 10-minute chunks

def _get_ffmpeg_path(tool: str) -> str:
    """
    In a PyInstaller bundle, FFmpeg is extracted to a temp directory.
    sys._MEIPASS points to that directory.
    Falls back to PATH lookup for development.
    """
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)
        tool_path = bundle_dir / f"{tool}.exe"
        if tool_path.exists():
            return str(tool_path)
    return tool  # Development: rely on PATH

def get_duration(audio_path: Path) -> float:
    """
    Return the duration of an audio file in seconds using FFprobe.
    Raises AudioProcessingError if FFprobe is unavailable or the file is unreadable.
    """
    logger.info({"event": "audio_probe_start", "path": str(audio_path)})
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        str(audio_path)
    ]
    result = _run(cmd)
    try:
        data = json.loads(result.stdout)
        duration = float(data["streams"][0]["duration"])
        logger.info({"event": "audio_probe_ok", "duration_s": duration})
        return duration
    except (KeyError, IndexError, ValueError, json.JSONDecodeError) as e:
        raise AudioProcessingError(f"Could not parse FFprobe output: {e}") from e


def compress_audio(input_path: Path, output_path: Path, bitrate: str = "64k") -> Path:
    """
    Re-encode audio to mono MP3 at a reduced bitrate.
    Reduces file size before sending to Groq — cuts API costs and latency.
    16kHz mono is sufficient for speech transcription.

    Returns the path to the compressed file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info({"event": "audio_compress_start", "input": str(input_path), "bitrate": bitrate})
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-ac", "1",         # mono
        "-ar", "16000",     # 16kHz
        "-b:a", bitrate,
        str(output_path)
    ]
    _run(cmd)
    logger.info({"event": "audio_compress_ok", "output": str(output_path)})
    return output_path


def needs_chunking(audio_path: Path) -> bool:
    """Return True if the file exceeds Groq's 25MB per-request limit."""
    return audio_path.stat().st_size > GROQ_MAX_BYTES


def split_into_chunks(
    audio_path: Path,
    output_dir: Path,
    chunk_duration: int = CHUNK_DURATION_SECONDS,
) -> list[Path]:
    """
    Split audio into fixed-duration chunks using FFmpeg's segment muxer.
    Returns a list of chunk file paths in order.

    Chunks are named: chunk_000.mp3, chunk_001.mp3, etc.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    chunk_pattern = str(output_dir / "chunk_%03d.mp3")

    logger.info({
        "event": "audio_split_start",
        "path": str(audio_path),
        "chunk_duration_s": chunk_duration
    })
    cmd = [
        "ffmpeg", "-y",
        "-i", str(audio_path),
        "-f", "segment",
        "-segment_time", str(chunk_duration),
        "-c", "copy",
        chunk_pattern
    ]
    _run(cmd)

    chunks = sorted(output_dir.glob("chunk_*.mp3"))
    logger.info({"event": "audio_split_ok", "chunk_count": len(chunks)})
    return chunks


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    # Replace bare "ffmpeg"/"ffprobe" with resolved paths
    if cmd[0] in ("ffmpeg", "ffprobe"):
        cmd[0] = _get_ffmpeg_path(cmd[0])

    if result.returncode != 0:
        raise AudioProcessingError(
            f"Command failed (exit {result.returncode}):\n"
            f"CMD: {' '.join(cmd)}\n"
            f"STDERR: {result.stderr}"
        )
    return result