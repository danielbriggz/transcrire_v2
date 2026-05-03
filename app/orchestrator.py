import time
import threading
from storage.db import get_connection
from storage.repositories.jobs_repo import JobsRepository
from storage.repositories.episodes_repo import EpisodesRepository
from storage.repositories.assets_repo import AssetsRepository
from domain.enums import Stage
from domain.models import Job
from workers.fetch_worker import FetchWorker
from workers.transcribe_worker import TranscribeWorker
from workers.caption_worker import CaptionWorker
from workers.image_worker import ImageWorker
from app.logging import get_logger

logger = get_logger(__name__)

POLL_INTERVAL = 2   # seconds between queue checks


class Orchestrator:
    """
    Polls the job queue and dispatches QUEUED jobs to their workers.
    Runs in a background thread — started once on app startup.
    """

    def __init__(self):
        self._running = False
        self._thread: threading.Thread = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info({"event": "orchestrator_started"})

    def stop(self) -> None:
        self._running = False
        logger.info({"event": "orchestrator_stopped"})

    def _loop(self) -> None:
        while self._running:
            try:
                conn = get_connection()
                jobs_repo = JobsRepository(conn)

                # Recover stale jobs on every poll cycle
                stale = jobs_repo.mark_stale_jobs()
                if stale:
                    logger.warning({"event": "stale_jobs_requeued", "count": len(stale)})

                job = jobs_repo.fetch_next_queued()
                if job:
                    self._dispatch(job, conn)
            except Exception as e:
                logger.error({"event": "orchestrator_loop_error", "error": str(e)})
            time.sleep(POLL_INTERVAL)

    def _dispatch(self, job: Job, conn) -> None:
        jobs_repo = JobsRepository(conn)
        episodes_repo = EpisodesRepository(conn)
        assets_repo = AssetsRepository(conn)

        logger.info({"event": "dispatching_job", "job_id": job.id, "stage": job.stage.value})

        worker_map = {
            Stage.FETCH:      lambda: FetchWorker(job, jobs_repo, episodes_repo, assets_repo),
            Stage.TRANSCRIBE: lambda: TranscribeWorker(job, jobs_repo, assets_repo),
            Stage.CAPTION:    lambda: CaptionWorker(job, jobs_repo, assets_repo, episodes_repo),
            Stage.IMAGE:      lambda: ImageWorker(job, jobs_repo, assets_repo),
        }

        factory = worker_map.get(job.stage)
        if not factory:
            logger.error({"event": "unknown_stage", "stage": job.stage.value})
            return

        worker = factory()
        # Run in a new thread so the poll loop stays responsive
        thread = threading.Thread(target=worker.execute, daemon=True)
        thread.start()


# Shared instance — started in app/lifecycle.py
orchestrator = Orchestrator()