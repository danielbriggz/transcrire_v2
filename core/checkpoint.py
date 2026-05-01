import json
from typing import Optional

from storage.repositories.jobs_repo import JobsRepository
from app.logging import get_logger

logger = get_logger(__name__)


class Checkpoint:
    """
    Persists and retrieves stage progress for a specific job.

    Checkpoints are stored in the jobs table's metadata_json column.
    Any stage can save progress mid-execution and resume from where
    it left off if the process is interrupted.

    Usage:
        cp = Checkpoint(job_id="abc123", jobs_repo=repo)
        cp.save({"last_chunk_index": 3, "segments": [...], "time_offset": 180.0})
        state = cp.load()   # returns the dict, or None if no checkpoint exists
    """

    def __init__(self, job_id: str, jobs_repo: JobsRepository):
        self._job_id = job_id
        self._repo = jobs_repo

    def save(self, data: dict) -> None:
        """Persist checkpoint data for this job."""
        self._repo.set_metadata(self._job_id, data)
        logger.debug({"event": "checkpoint_saved", "job_id": self._job_id})

    def load(self) -> Optional[dict]:
        """Load checkpoint data. Returns None if none exists."""
        job = self._repo.get_by_id(self._job_id)
        if not job or not job.metadata_json:
            return None
        try:
            return (
                json.loads(job.metadata_json)
                if isinstance(job.metadata_json, str)
                else job.metadata_json
            )
        except (json.JSONDecodeError, TypeError):
            logger.warning({"event": "checkpoint_corrupt", "job_id": self._job_id})
            return None

    def clear(self) -> None:
        """Remove checkpoint data after a stage completes successfully."""
        self._repo.set_metadata(self._job_id, {})
        logger.debug({"event": "checkpoint_cleared", "job_id": self._job_id})