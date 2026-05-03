import threading
from datetime import datetime, timezone
from domain.models import Job
from domain.enums import JobStatus
from storage.repositories.jobs_repo import JobsRepository
from storage.write_aggregator import WriteAggregator
from events.emitter import emitter
from app.logging import get_logger

logger = get_logger(__name__)

HEARTBEAT_INTERVAL = 5  # seconds


class BaseWorker:
    """
    All workers inherit from this class.
    Handles heartbeat, status transitions, and error reporting.
    Subclasses implement run_stage().
    """

    def __init__(self, job: Job, jobs_repo: JobsRepository):
        self._job = job
        self._jobs_repo = jobs_repo
        self._heartbeat_thread: threading.Timer = None
        self._running = False

    def execute(self) -> None:
        """Called by the orchestrator. Manages lifecycle around run_stage()."""
        self._jobs_repo.update_status(self._job.id, JobStatus.RUNNING)
        self._jobs_repo.increment_attempt(self._job.id)
        self._start_heartbeat()

        emitter.emit("stage_started", {
            "job_id": self._job.id,
            "stage": self._job.stage.value,
            "episode_id": self._job.episode_id,
        })

        try:
            self.run_stage()
            self._jobs_repo.update_status(self._job.id, JobStatus.SUCCESS)
            emitter.emit("stage_completed", {
                "job_id": self._job.id,
                "stage": self._job.stage.value,
                "episode_id": self._job.episode_id,
            })
            logger.info({"event": "worker_success", "job_id": self._job.id})
        except Exception as e:
            self._jobs_repo.update_status(self._job.id, JobStatus.FAILED)
            emitter.emit("stage_failed", {
                "job_id": self._job.id,
                "stage": self._job.stage.value,
                "episode_id": self._job.episode_id,
                "error": str(e),
            })
            logger.error({"event": "worker_failed", "job_id": self._job.id, "error": str(e)})
            raise
        finally:
            self._stop_heartbeat()

    def run_stage(self) -> None:
        """Override in subclasses. Contains the stage-specific logic."""
        raise NotImplementedError

    def _start_heartbeat(self) -> None:
        self._running = True
        self._heartbeat_tick()

    def _stop_heartbeat(self) -> None:
        self._running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.cancel()

    def _heartbeat_tick(self) -> None:
        if not self._running:
            return
        self._jobs_repo.update_heartbeat(self._job.id)
        self._heartbeat_thread = threading.Timer(HEARTBEAT_INTERVAL, self._heartbeat_tick)
        self._heartbeat_thread.daemon = True
        self._heartbeat_thread.start()