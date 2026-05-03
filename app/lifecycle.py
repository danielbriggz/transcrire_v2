from storage.db import get_connection, run_migrations
from storage.repositories.jobs_repo import JobsRepository
from app.logging import get_logger

logger = get_logger(__name__)


def startup() -> None:
    """
    Run on application start before the GUI is shown.
    1. Run DB migrations (idempotent — safe on every start)
    2. Recover any stale RUNNING jobs from a previous crashed session
    """
    logger.info({"event": "app_startup_begin"})

    conn = get_connection()
    run_migrations(conn)
    logger.info({"event": "migrations_ok"})

    jobs_repo = JobsRepository(conn)
    stale = jobs_repo.mark_stale_jobs()
    if stale:
        logger.warning({"event": "stale_jobs_recovered", "count": len(stale), "ids": stale})

    logger.info({"event": "app_startup_complete"})

    # Add to the end of startup():
    from app.orchestrator import orchestrator
    orchestrator.start()


def shutdown() -> None:
    """Run on application shutdown. Placeholder for cleanup."""
    logger.info({"event": "app_shutdown"})

    # Add to shutdown():
    from app.orchestrator import orchestrator
    orchestrator.stop()