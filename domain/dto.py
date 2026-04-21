from dataclasses import dataclass
from domain.enums import Stage, TranscribeMode, TranscriptType


@dataclass
class JobPayload:
    """Passed to the queue when a stage is enqueued."""
    episode_id: str
    stage: Stage
    params: dict   # pyright: ignore[reportMissingTypeArgument] # Stage-specific parameters (flexible)


@dataclass
class TranscribeParams:
    """Params specific to the TRANSCRIBE stage."""
    mode: TranscribeMode
    transcript_type: TranscriptType
    audio_path: str


@dataclass
class FetchParams:
    """Params specific to the FETCH stage."""
    feed_url: str
    season: Optional[int] # pyright: ignore[reportUndefinedVariable]  # noqa: F821
    episode_number: int