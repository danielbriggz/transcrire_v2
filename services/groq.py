from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass, field

from groq import Groq
from groq import APIStatusError, APITimeoutError, APIConnectionError

from utils.retry import with_standard_retry, TransientError, PermanentError, TranscriptionError
from app.config import config
from app.logging import get_logger

logger = get_logger(__name__)

_client: Optional[Groq] = None


def _get_client() -> Groq:
    """
    Return the shared Groq client, creating it on first call.
    Validates the API key is present before attempting connection.
    This is lazy — the client is not created at import time.
    """
    global _client
    if _client is None:
        if not config.groq_api_key:
            raise PermanentError("GROQ_API_KEY is not set. Add it to your .env file.")
        _client = Groq(api_key=config.groq_api_key)
        logger.info({"event": "groq_client_initialised"})
    return _client


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass
class GroqTranscriptResult:
    """Structured result from a Groq transcription call."""
    full_text: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    language: Optional[str] = None
    duration_s: Optional[float] = None


@with_standard_retry
def transcribe_file(
    audio_path: Path,
    language: str = "en",
    response_format: str = "verbose_json",
) -> GroqTranscriptResult:
    """
    Transcribe a single audio file via Groq's Whisper Large v3.

    Args:
        audio_path:      Path to the audio file. Must be under 25MB.
        language:        ISO 639-1 language code. Default: "en".
        response_format: "verbose_json" returns segments. "text" returns plain string.

    Raises:
        TransientError:     Rate limit, timeout, or server error — will retry.
        PermanentError:     Bad API key or unsupported format — will not retry.
        TranscriptionError: Unexpected response structure.
    """
    client = _get_client()
    logger.info({"event": "groq_transcribe_start", "path": str(audio_path)})

    try:
        with open(audio_path, "rb") as f:
            response = client.audio.transcriptions.create(
                file=(audio_path.name, f),
                model="whisper-large-v3",
                language=language,
                response_format=response_format,
            )
    except APITimeoutError as e:
        raise TransientError(f"Groq request timed out: {e}") from e
    except APIConnectionError as e:
        raise TransientError(f"Groq connection error: {e}") from e
    except APIStatusError as e:
        if e.status_code in (429, 503, 502):
            raise TransientError(f"Groq rate limit or server error: {e.status_code}") from e
        if e.status_code in (401, 403):
            raise PermanentError(f"Groq authentication failed: {e.status_code}") from e
        raise TranscriptionError(f"Groq API error {e.status_code}: {e.message}") from e

    result = _parse_response(response, response_format)
    logger.info({"event": "groq_transcribe_ok", "chars": len(result.full_text)})
    return result


def transcribe_chunks(
    chunk_paths: list[Path],
    checkpoint_save_fn: Optional[Callable] = None,
    checkpoint_load_fn: Optional[Callable] = None,
    language: str = "en",
) -> GroqTranscriptResult:
    """
    Transcribe a list of audio chunks in order, with checkpoint resume support.

    Args:
        chunk_paths:        Ordered list of chunk file paths.
        checkpoint_save_fn: Optional callable(index, segments, time_offset).
                            Called after each chunk to persist progress.
        checkpoint_load_fn: Optional callable() returning a dict with
                            "last_chunk_index", "segments", "time_offset".
        language:           ISO 639-1 language code.

    Returns:
        A merged GroqTranscriptResult with all segments in correct time order.
    """
    start_index = 0
    accumulated_segments: list[TranscriptSegment] = []
    time_offset = 0.0

    if checkpoint_load_fn:
        saved = checkpoint_load_fn()
        if saved and "last_chunk_index" in saved:
            start_index = saved["last_chunk_index"] + 1
            accumulated_segments = [
                TranscriptSegment(**s) for s in saved.get("segments", [])
            ]
            time_offset = saved.get("time_offset", 0.0)
            logger.info({"event": "groq_checkpoint_resume", "resuming_from": start_index})

    for i, chunk_path in enumerate(chunk_paths):
        if i < start_index:
            continue

        logger.info({"event": "groq_chunk_start", "chunk": i + 1, "total": len(chunk_paths)})
        result = transcribe_file(chunk_path, language=language)

        for seg in result.segments:
            accumulated_segments.append(TranscriptSegment(
                start=seg.start + time_offset,
                end=seg.end + time_offset,
                text=seg.text,
            ))

        time_offset += (result.duration_s or 0.0)

        if checkpoint_save_fn:
            checkpoint_save_fn(
                i,
                [{"start": s.start, "end": s.end, "text": s.text} for s in accumulated_segments],
                time_offset,
            )

    full_text = " ".join(s.text.strip() for s in accumulated_segments)
    return GroqTranscriptResult(full_text=full_text, segments=accumulated_segments, language=language)


def _parse_response(response, response_format: str) -> GroqTranscriptResult:
    if response_format == "verbose_json":
        segments = [
            TranscriptSegment(start=seg.start, end=seg.end, text=seg.text)
            for seg in getattr(response, "segments", [])
        ]
        return GroqTranscriptResult(
            full_text=response.text,
            segments=segments,
            language=getattr(response, "language", None),
            duration_s=getattr(response, "duration", None),
        )
    return GroqTranscriptResult(full_text=str(response))