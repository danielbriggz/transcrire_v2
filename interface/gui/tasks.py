import asyncio
import threading
from typing import Callable, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from events.emitter import emitter
from app.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TaskState:
    """Tracks a single running background task."""
    task_id: str
    episode_id: str
    stage: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    progress_pct: Optional[float] = None
    is_complete: bool = False
    error: Optional[str] = None


# Global registry of active tasks — keyed by task_id
_active_tasks: dict[str, TaskState] = {}


def run_stage_in_background(
    task_id: str,
    episode_id: str,
    stage: str,
    worker_fn: Callable,
    on_complete: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
) -> TaskState:
    """
    Execute a pipeline stage function in a background thread.

    Args:
        task_id:    Unique identifier for this task (use job_id).
        episode_id: Episode being processed.
        stage:      Stage name for logging and UI display.
        worker_fn:  The function to run (e.g. a worker's .run() method).
        on_complete: Optional callback fired on success (runs in background thread).
        on_error:   Optional callback fired on failure with the exception.

    Returns:
        A TaskState object that reflects live task progress.
    """
    state = TaskState(task_id=task_id, episode_id=episode_id, stage=stage)
    _active_tasks[task_id] = state

    emitter.emit("stage_started", {"task_id": task_id, "stage": stage, "episode_id": episode_id})
    logger.info({"event": "background_task_start", "task_id": task_id, "stage": stage})

    def _run():
        try:
            worker_fn()
            state.is_complete = True
            state.progress_pct = 100.0
            emitter.emit("stage_completed", {
                "task_id": task_id,
                "stage": stage,
                "episode_id": episode_id,
            })
            logger.info({"event": "background_task_complete", "task_id": task_id})
            if on_complete:
                on_complete()
        except Exception as e:
            state.error = str(e)
            state.is_complete = True
            emitter.emit("stage_failed", {
                "task_id": task_id,
                "stage": stage,
                "episode_id": episode_id,
                "error": str(e),
            })
            logger.error({"event": "background_task_failed", "task_id": task_id, "error": str(e)})
            if on_error:
                on_error(e)
        finally:
            _active_tasks.pop(task_id, None)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return state


def get_task_state(task_id: str) -> Optional[TaskState]:
    """Return the current state of a running task, or None if not found."""
    return _active_tasks.get(task_id)


def is_task_running(episode_id: str) -> bool:
    """Return True if any task is currently running for the given episode."""
    return any(t.episode_id == episode_id for t in _active_tasks.values())