import uuid
from datetime import datetime, timezone
from typing import Optional
from domain.models import Job

from domain.enums import Stage, JobStatus
from storage.db import get_cursor, get_connection
from app.logging import get_logger

logger = get_logger(__name__)

# How long (seconds) before a RUNNING job is considered stale
HEARTBEAT_TIMEOUT_SECONDS = 60


class JobsRepository:
    def __init__(self, conn=None):
        self._conn = conn or get_connection()

    def create(self, episode_id: str, stage: Stage) -> Job:
        job = Job(
            id=str(uuid.uuid4()),
            episode_id=episode_id,
            stage=stage,
            status=JobStatus.QUEUED,
            attempt_count=0,
        )
        with get_cursor(self._conn) as cur:
            cur.execute(
                """
                INSERT INTO jobs (id, episode_id, stage, status, attempt_count, updated_at)
                VALUES (?, ?, ?, 'QUEUED', 0, ?)
                """,
                (job.id, episode_id, stage.value,
                 datetime.now(timezone.utc).isoformat())
            )
        logger.info({"event": "job_created", "id": job.id, "stage": stage.value})
        return job

    def fetch_next_queued(self) -> Optional[Job]:
        """Fetch the oldest QUEUED job. Returns None if queue is empty."""
        with get_cursor(self._conn) as cur:
            cur.execute(
                """
                SELECT * FROM jobs
                WHERE status = 'QUEUED'
                ORDER BY rowid ASC
                LIMIT 1
                """
            )
            row = cur.fetchone()
        return self._row_to_job(row) if row else None

    def update_status(self, job_id: str, status: JobStatus) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with get_cursor(self._conn) as cur:
            cur.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                (status.value, now, job_id)
            )
        logger.debug({"event": "job_status_updated", "id": job_id, "status": status.value})

    def update_heartbeat(self, job_id: str) -> None:
        """Call this every ~5 seconds from a running worker."""
        now = datetime.now(timezone.utc).isoformat()
        with get_cursor(self._conn) as cur:
            cur.execute(
                "UPDATE jobs SET heartbeat_at = ? WHERE id = ?",
                (now, job_id)
            )

    def mark_stale_jobs(self) -> list[str]:
        """
        Find RUNNING jobs whose heartbeat has expired.
        Marks them RETRYABLE and returns their IDs.
        Called by the orchestrator on startup and periodically.
        """
        with get_cursor(self._conn) as cur:
            cur.execute("SELECT id, heartbeat_at FROM jobs WHERE status = 'RUNNING'")
            running = cur.fetchall()

        now = datetime.now(timezone.utc)
        stale_ids = []

        for row in running:
            if not row["heartbeat_at"]:
                stale_ids.append(row["id"])
                continue
            last_beat = datetime.fromisoformat(row["heartbeat_at"])
            if (now - last_beat).total_seconds() > HEARTBEAT_TIMEOUT_SECONDS:
                stale_ids.append(row["id"])

        for job_id in stale_ids:
            self.update_status(job_id, JobStatus.RETRYABLE)
            logger.warning({"event": "stale_job_marked_retryable", "id": job_id})

        return stale_ids

    def increment_attempt(self, job_id: str) -> None:
        with get_cursor(self._conn) as cur:
            cur.execute(
                "UPDATE jobs SET attempt_count = attempt_count + 1 WHERE id = ?",
                (job_id,)
            )

    def get_by_id(self, job_id: str) -> Optional[Job]:
        with get_cursor(self._conn) as cur:
            cur.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = cur.fetchone()
        return self._row_to_job(row) if row else None

    def get_jobs_for_episode(self, episode_id: str) -> list[Job]:
        with get_cursor(self._conn) as cur:
            cur.execute(
                "SELECT * FROM jobs WHERE episode_id = ? ORDER BY rowid ASC",
                (episode_id,)
            )
            rows = cur.fetchall()
        return [self._row_to_job(r) for r in rows]

    def _row_to_job(self, row: dict) -> Job:
        return Job(
            id=row["id"],
            episode_id=row["episode_id"],
            stage=Stage(row["stage"]),
            status=JobStatus(row["status"]),
            attempt_count=row["attempt_count"],
            execution_id=row["execution_id"],
            worker_id=row["worker_id"],
            heartbeat_at=datetime.fromisoformat(row["heartbeat_at"]) if row["heartbeat_at"] else None,
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )
    
    def set_metadata(self, job_id: str, data: dict) -> None:
        import json
        with get_cursor(self._conn) as cur:
            cur.execute(
                "UPDATE jobs SET metadata_json = ? WHERE id = ?",
                (json.dumps(data), job_id)
            )