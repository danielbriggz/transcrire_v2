from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from domain.enums import Stage, JobStatus, AssetType


@dataclass
class Episode:
    id: str                            # UUID string
    title: str
    published_date: Optional[str]      # ISO date string from RSS
    created_at: datetime = field(default_factory=datetime.utcnow) # type: ignore


@dataclass
class Job:
    id: str                            # UUID string
    episode_id: str
    stage: Stage
    status: JobStatus
    attempt_count: int = 0
    execution_id: Optional[str] = None
    heartbeat_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata_json: Optional[str] = None
    worker_id: Optional[str] = None


@dataclass
class StageResult:
    id: str
    job_id: str
    episode_id: str
    stage: Stage
    status: JobStatus
    duration_ms: Optional[int] = None
    metadata_json: Optional[dict] = None # type: ignore
    error_log: Optional[str] = None


@dataclass
class Asset:
    id: str
    episode_id: str
    asset_type: AssetType
    file_path: str
    checksum: str
    version: int = 1
    is_active: bool = True