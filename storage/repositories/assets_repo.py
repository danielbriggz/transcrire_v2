import uuid
from datetime import datetime, timezone
from typing import Optional

from domain.models import Asset
from domain.enums import AssetType
from storage.db import get_cursor, get_connection
from app.logging import get_logger

logger = get_logger(__name__)


class AssetsRepository:
    def __init__(self, conn=None):
        self._conn = conn or get_connection()

    def register(self, episode_id: str, asset_type: AssetType,
                 file_path: str, checksum: str) -> Asset:
        """
        Register a new asset. Deactivates any existing active asset
        of the same type for the same episode before inserting.
        """
        self._deactivate_existing(episode_id, asset_type)

        asset = Asset(
            id=str(uuid.uuid4()),
            episode_id=episode_id,
            asset_type=asset_type,
            file_path=file_path,
            checksum=checksum,
        )
        # Determine version number
        version = self._next_version(episode_id, asset_type)
        asset.version = version

        with get_cursor(self._conn) as cur:
            cur.execute(
                """
                INSERT INTO assets
                    (id, episode_id, asset_type, file_path, checksum, version, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (asset.id, episode_id, asset_type.value, file_path,
                 checksum, version, datetime.now(timezone.utc).isoformat())
            )
        logger.info({
            "event": "asset_registered",
            "id": asset.id,
            "type": asset_type.value,
            "version": version
        })
        return asset

    def get_active(self, episode_id: str, asset_type: AssetType) -> Optional[Asset]:
        """Returns the current active asset of a given type for an episode."""
        with get_cursor(self._conn) as cur:
            cur.execute(
                """
                SELECT * FROM assets
                WHERE episode_id = ? AND asset_type = ? AND is_active = 1
                """,
                (episode_id, asset_type.value)
            )
            row = cur.fetchone()
        return self._row_to_asset(row) if row else None

    def checksum_matches(self, episode_id: str, asset_type: AssetType,
                         checksum: str) -> bool:
        """
        Returns True if the active asset's checksum matches the given value.
        Used by pipeline idempotency checks — if True, skip reprocessing.
        """
        asset = self.get_active(episode_id, asset_type)
        return asset is not None and asset.checksum == checksum

    def _deactivate_existing(self, episode_id: str, asset_type: AssetType) -> None:
        with get_cursor(self._conn) as cur:
            cur.execute(
                """
                UPDATE assets SET is_active = 0
                WHERE episode_id = ? AND asset_type = ? AND is_active = 1
                """,
                (episode_id, asset_type.value)
            )

    def _next_version(self, episode_id: str, asset_type: AssetType) -> int:
        with get_cursor(self._conn) as cur:
            cur.execute(
                """
                SELECT MAX(version) as max_version FROM assets
                WHERE episode_id = ? AND asset_type = ?
                """,
                (episode_id, asset_type.value)
            )
            row = cur.fetchone()
        return (row["max_version"] or 0) + 1

    def _row_to_asset(self, row) -> Asset:
        return Asset(
            id=row["id"],
            episode_id=row["episode_id"],
            asset_type=AssetType(row["asset_type"]),
            file_path=row["file_path"],
            checksum=row["checksum"],
            version=row["version"],
            is_active=bool(row["is_active"]),
        )