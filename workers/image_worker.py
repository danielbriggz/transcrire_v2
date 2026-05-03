from pathlib import Path
from domain.models import Job
from storage.repositories.jobs_repo import JobsRepository
from storage.repositories.assets_repo import AssetsRepository
from storage.files import compute_checksum
from core.images import render_quote_card, QuoteCardConfig
from domain.enums import AssetType
from workers.base_worker import BaseWorker
from app.config import config
from app.logging import get_logger
import json

logger = get_logger(__name__)


class ImageWorker(BaseWorker):
    """
    IMAGE stage worker.
    Reads transcript for quote text, renders 1080x1080 quote card.
    Params in job metadata_json (optional):
        quote_text: str — override auto-selected quote
    """

    def __init__(self, job: Job, jobs_repo: JobsRepository, assets_repo: AssetsRepository):
        super().__init__(job, jobs_repo)
        self._assets_repo = assets_repo

    def run_stage(self) -> None:
        params = json.loads(self._job.metadata_json or "{}")

        cover_asset = self._assets_repo.get_active(self._job.episode_id, AssetType.COVER_ART)
        if not cover_asset:
            raise ValueError("No cover art asset found. Run FETCH stage first.")

        transcript_asset = self._assets_repo.get_active(
            self._job.episode_id, AssetType.TRANSCRIPT
        )

        # Use provided quote or first 280 chars of transcript
        quote_text = params.get("quote_text")
        if not quote_text and transcript_asset:
            full_text = Path(transcript_asset.file_path).read_text(encoding="utf-8")
            quote_text = full_text[:280].rsplit(" ", 1)[0]  # cut at word boundary

        if not quote_text:
            raise ValueError("No quote text available. Provide quote_text in params or run TRANSCRIBE first.")

        episode_dir = config.output_dir / self._job.episode_id
        output_path = episode_dir / "quote_card.jpg"

        card_config = QuoteCardConfig(
            quote_text=quote_text,
            cover_art_path=Path(cover_asset.file_path),
            output_path=output_path,
        )
        render_quote_card(card_config)

        checksum = compute_checksum(output_path)
        self._assets_repo.register(
            self._job.episode_id, AssetType.IMAGE, str(output_path), checksum
        )

        logger.info({"event": "image_complete", "episode_id": self._job.episode_id})