import uuid
from datetime import datetime, timezone
from typing import Optional

from domain.models import Episode
from storage.db import get_cursor, get_connection
from app.logging import get_logger

logger = get_logger(__name__)


class EpisodesRepository:
    def __init__(self, conn=None):
        self._conn = conn or get_connection()

    def create(self, title: str, published_date: str = None, feed_url: str = None) -> Episode:
        episode = Episode(
            id=str(uuid.uuid4()),
            title=title,
            published_date=published_date,
            created_at=datetime.now(timezone.utc),
        )
        with get_cursor(self._conn) as cur:
            cur.execute(
                """
                INSERT INTO episodes (id, title, published_date, feed_url, status, created_at)
                VALUES (?, ?, ?, ?, 'NEW', ?)
                """,
                (episode.id, episode.title, episode.published_date,
                 feed_url, episode.created_at.isoformat())
            )
        logger.info({"event": "episode_created", "id": episode.id, "title": title})
        return episode

    def get_by_id(self, episode_id: str) -> Optional[Episode]:
        with get_cursor(self._conn) as cur:
            cur.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,))
            row = cur.fetchone()
        if not row:
            return None
        return Episode(
            id=row["id"],
            title=row["title"],
            published_date=row["published_date"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def list_all(self) -> list[Episode]:
        with get_cursor(self._conn) as cur:
            cur.execute("SELECT * FROM episodes ORDER BY created_at DESC")
            rows = cur.fetchall()
        return [
            Episode(
                id=r["id"],
                title=r["title"],
                published_date=r["published_date"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    def update_status(self, episode_id: str, status: str) -> None:
        with get_cursor(self._conn) as cur:
            cur.execute(
                "UPDATE episodes SET status = ? WHERE id = ?",
                (status, episode_id)
            )
        logger.debug({"event": "episode_status_updated", "id": episode_id, "status": status})

    def delete(self, episode_id: str) -> None:
        """Hard delete. Use with caution — cascades are not automatic."""
        with get_cursor(self._conn) as cur:
            cur.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
        logger.warning({"event": "episode_deleted", "id": episode_id})