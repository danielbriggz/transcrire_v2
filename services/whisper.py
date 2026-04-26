from pathlib import Path
from typing import Optional

from utils.retry import TranscriptionError, PermanentError
from services.groq import GroqTranscriptResult, TranscriptSegment
from app.logging import get_logger

logger = get_logger(__name__)

_whisper = None


def _get_whisper():
    """
    Lazy import of the whisper library.
    Not imported at module level — cloud-only users don't have it installed.
    """
    global _whisper
    if _whisper is None:
        try:
            import whisper
            _whisper = whisper
        except ImportError as e:
            raise PermanentError(
                "openai-whisper is not installed. Run: uv add openai-whisper"
            ) from e
    return _whisper


def transcribe_file(
    audio_path: Path,
    model_size: str = "base",
    language: Optional[str] = "en",
) -> GroqTranscriptResult:
    """
    Transcribe an audio file locally using OpenAI Whisper.

    Returns the same GroqTranscriptResult type as services/groq.py so the
    pipeline layer requires no conditional logic between cloud and local paths.

    Args:
        audio_path:  Path to audio file. No size limit — runs entirely locally.
        model_size:  Whisper model: tiny, base, small, medium, large.
                     Larger = more accurate, slower, more RAM.
        language:    ISO 639-1 code, or None for auto-detection.
    """
    whisper = _get_whisper()
    logger.info({
        "event": "whisper_transcribe_start",
        "path": str(audio_path),
        "model": model_size
    })

    try:
        model = whisper.load_model(model_size)
        result = model.transcribe(str(audio_path), language=language, verbose=False)
    except Exception as e:
        raise TranscriptionError(f"Whisper transcription failed: {e}") from e

    segments = [
        TranscriptSegment(start=seg["start"], end=seg["end"], text=seg["text"])
        for seg in result.get("segments", [])
    ]

    logger.info({
        "event": "whisper_transcribe_ok",
        "chars": len(result.get("text", "")),
        "segments": len(segments)
    })

    return GroqTranscriptResult(
        full_text=result.get("text", ""),
        segments=segments,
        language=result.get("language"),
    )