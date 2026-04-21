from enum import Enum


class Stage(str, Enum):
    FETCH = "FETCH"
    TRANSCRIBE = "TRANSCRIBE"
    CAPTION = "CAPTION"
    IMAGE = "IMAGE"


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    RETRYABLE = "RETRYABLE"


class TranscribeMode(str, Enum):
    CLOUD = "CLOUD"       # Groq
    LOCAL = "LOCAL"       # Whisper


class TranscriptType(str, Enum):
    PLAIN = "PLAIN"
    SEGMENT = "SEGMENT"   # Segment-level timestamps
    WORD = "WORD"         # Word-level timestamps


class AssetType(str, Enum):
    AUDIO = "audio"
    COVER_ART = "cover_art"
    TRANSCRIPT = "transcript"
    CAPTION = "caption"
    IMAGE = "image"
    RAW_DATA = "raw_data"


class FetchChoice(str, Enum):
    RSS = "RSS"
    LOCAL = "LOCAL"