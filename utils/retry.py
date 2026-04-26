import logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


# ─── Typed Exception Hierarchy ────────────────────────────────────────────────

class TranscrireServiceError(Exception):
    """Base class for all external service errors."""
    pass

class TransientError(TranscrireServiceError):
    """Temporary failure — safe to retry. E.g. rate limit, timeout, 503."""
    pass

class PermanentError(TranscrireServiceError):
    """Non-recoverable failure — do not retry. E.g. bad API key, 404."""
    pass

class AudioProcessingError(TranscrireServiceError):
    """FFmpeg/FFprobe failure."""
    pass

class TranscriptionError(TranscrireServiceError):
    """Groq or Whisper transcription failure."""
    pass

class CaptionError(TranscrireServiceError):
    """Gemini caption generation failure."""
    pass

class RSSError(TranscrireServiceError):
    """Feed fetch or parse failure."""
    pass


# ─── Retry Decorators ─────────────────────────────────────────────────────────

def with_standard_retry(func):
    """
    Standard retry for API calls.
    - 3 attempts total
    - Exponential backoff: 2s, 4s
    - Only retries TransientError subclasses
    """
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(TransientError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )(func)


def with_aggressive_retry(func):
    """
    Aggressive retry for rate-limited services (e.g. Gemini free tier).
    - 5 attempts total
    - Exponential backoff: 4s, 8s, 16s, 32s
    """
    return retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type(TransientError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )(func)