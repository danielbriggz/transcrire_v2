import uuid
import json
from datetime import datetime, timezone
from typing import Optional

from storage.db import get_cursor, get_connection
from app.logging import get_logger

logger = get_logger(__name__)


class EventsRepository:
    """
    Append-only durable event log.
    Rows are NEVER updated or deleted — only inserted.
    """

    def __init__(self, conn=None):
        self._conn = conn or get_connection()

    def append(self, job_id: str, episode_id: str,
               event_type: str, payload: dict = None) -> str:
        event_id = str(uuid.uuid4())
        with get_cursor(self._conn) as cur:
            cur.execute(
                """
                INSERT INTO events (id, job_id, episode_id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    job_id,
                    episode_id,
                    event_type,
                    json.dumps(payload or {}),
                    datetime.now(timezone.utc).isoformat()
                )
            )
        return event_id

    def get_for_job(self, job_id: str) -> list[dict]:
        with get_cursor(self._conn) as cur:
            cur.execute(
                "SELECT * FROM events WHERE job_id = ? ORDER BY rowid ASC",
                (job_id,)
            )
            rows = cur.fetchall()
        return [self._deserialise(r) for r in rows]

    def get_for_episode(self, episode_id: str) -> list[dict]:
        with get_cursor(self._conn) as cur:
            cur.execute(
                "SELECT * FROM events WHERE episode_id = ? ORDER BY rowid ASC",
                (episode_id,)
            )
            rows = cur.fetchall()
        return [self._deserialise(r) for r in rows]

    def _deserialise(self, row) -> dict:
        return {
            "id": row["id"],
            "job_id": row["job_id"],
            "episode_id": row["episode_id"],
            "event_type": row["event_type"],
            "payload": json.loads(row["payload_json"] or "{}"),
            "created_at": row["created_at"],
        }