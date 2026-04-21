import threading
from typing import Callable
from app.logging import get_logger

logger = get_logger(__name__)

DEFAULT_FLUSH_INTERVAL = 2.0   # seconds
DEFAULT_BATCH_SIZE = 10        # flush if this many writes are pending


class WriteAggregator:
    """
    Buffers write operations and flushes them in batches.

    Usage:
        aggregator = WriteAggregator(conn)
        aggregator.start()

        # Queue a write (non-blocking)
        aggregator.queue(lambda: jobs_repo.update_heartbeat(job_id))

        # Force immediate flush
        aggregator.flush()

        # Stop background flush loop on shutdown
        aggregator.stop()
    """

    def __init__(self, flush_interval: float = DEFAULT_FLUSH_INTERVAL,
                 batch_size: int = DEFAULT_BATCH_SIZE):
        self._queue: list[Callable] = []
        self._lock = threading.Lock()
        self._flush_interval = flush_interval
        self._batch_size = batch_size
        self._timer: threading.Timer = None
        self._running = False

    def start(self) -> None:
        self._running = True
        self._schedule_flush()
        logger.debug({"event": "write_aggregator_started"})

    def stop(self) -> None:
        self._running = False
        if self._timer:
            self._timer.cancel()
        self.flush()  # Final flush on shutdown
        logger.debug({"event": "write_aggregator_stopped"})

    def queue(self, write_fn: Callable) -> None:
        """Add a write operation to the buffer."""
        with self._lock:
            self._queue.append(write_fn)
            if len(self._queue) >= self._batch_size:
                self._flush_locked()

    def flush(self) -> None:
        """Force immediate execution of all buffered writes."""
        with self._lock:
            self._flush_locked()

    def _flush_locked(self) -> None:
        """Execute all queued writes. Must be called with self._lock held."""
        if not self._queue:
            return
        pending = self._queue.copy()
        self._queue.clear()
        errors = 0
        for fn in pending:
            try:
                fn()
            except Exception as e:
                errors += 1
                logger.error({"event": "write_aggregator_error", "error": str(e)})
        if errors:
            logger.warning({"event": "write_aggregator_flush_partial",
                            "total": len(pending), "errors": errors})
        else:
            logger.debug({"event": "write_aggregator_flush_ok", "count": len(pending)})

    def _schedule_flush(self) -> None:
        if not self._running:
            return
        self._timer = threading.Timer(self._flush_interval, self._timer_flush)
        self._timer.daemon = True
        self._timer.start()

    def _timer_flush(self) -> None:
        self.flush()
        self._schedule_flush()