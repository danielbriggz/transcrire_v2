from pathlib import Path
from typing import Optional

from domain.enums import AssetType
from storage.repositories.assets_repo import AssetsRepository
from storage.files import compute_checksum
from app.logging import get_logger

logger = get_logger(__name__)


def should_skip_stage(
    episode_id: str,
    asset_type: AssetType,
    assets_repo: AssetsRepository,
    current_file_path: Optional[Path] = None,
) -> bool:
    """
    Return True if a stage can be safely skipped.

    A stage is skippable when:
    1. An active asset of the given type exists in the DB for this episode
    2. The file at that path still exists on disk
    3. The file's current checksum matches the stored checksum

    Args:
        episode_id:        The episode being processed.
        asset_type:        The type of asset this stage would produce.
        assets_repo:       Repository for asset lookups.
        current_file_path: If provided, used for checksum comparison.
                           If None, the path stored in the DB record is used.
    """
    asset = assets_repo.get_active(episode_id, asset_type)

    if asset is None:
        logger.debug({"event": "idempotency_miss", "asset_type": asset_type.value})
        return False

    file_path = current_file_path or Path(asset.file_path)

    if not file_path.exists():
        logger.warning({"event": "idempotency_file_missing", "path": str(file_path)})
        return False

    match = compute_checksum(file_path) == asset.checksum
    logger.debug({"event": "idempotency_check", "asset_type": asset_type.value, "match": match})
    return match


def compute_params_fingerprint(params: dict) -> str:
    """
    Generate a deterministic fingerprint for a set of stage parameters.
    Used to detect when inputs have changed even if the output file exists.

    Example: switching transcription model from 'base' to 'large' changes
    the fingerprint, so should_skip_stage returns False even if a transcript exists.
    """
    from utils.hashing import sha256_dict
    return sha256_dict(params)