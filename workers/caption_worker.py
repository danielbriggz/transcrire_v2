import json
from pathlib import Path
from domain.models import Job
from storage.repositories.jobs_repo import JobsRepository
from storage.repositories.assets_repo import AssetsRepository
from storage.repositories.episodes_repo import EpisodesRepository
from storage.files import compute_checksum
from core.captions import generate_caption_bundle
from domain.enums import AssetType
from workers.base_worker import BaseWorker
from app.config import config
from app.logging import get_logger

logger = get_logger(__name__)


class CaptionWorker(BaseWorker):
    """
    CAPTION stage worker.
    Reads transcript, generates captions for all platforms, saves as JSON.
    """

    def __init__(self, job: Job, jobs_repo: JobsRepository,
                 assets_repo: AssetsRepository, episodes_repo: EpisodesRepository):
        super().__init__(job, jobs_repo)
        self._assets_repo = assets_repo
        self._episodes_repo = episodes_repo

    def run_stage(self) -> None:
        transcript_asset = self._assets_repo.get_active(
            self._job.episode_id, AssetType.TRANSCRIPT
        )
        if not transcript_asset:
            raise ValueError("No transcript asset found. Run TRANSCRIBE stage first.")

        transcript_text = Path(transcript_asset.file_path).read_text(encoding="utf-8")
        episode = self._episodes_repo.get_by_id(self._job.episode_id)
        episode_title = episode.title if episode else "Untitled"

        bundle = generate_caption_bundle(
            episode_id=self._job.episode_id,
            episode_title=episode_title,
            transcript_text=transcript_text,
            spotify_link=getattr(episode, "spotify_link", None),
        )

        episode_dir = config.output_dir / self._job.episode_id
        captions_path = episode_dir / "captions.json"
        captions_path.write_text(
            json.dumps(bundle.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        checksum = compute_checksum(captions_path)
        self._assets_repo.register(
            self._job.episode_id, AssetType.CAPTION, str(captions_path), checksum
        )

        if bundle.errors:
            logger.warning({"event": "caption_partial_errors", "errors": bundle.errors})

        logger.info({"event": "caption_complete", "episode_id": self._job.episode_id})