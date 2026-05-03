from pathlib import Path
from domain.models import Job
from storage.repositories.jobs_repo import JobsRepository
from storage.repositories.episodes_repo import EpisodesRepository
from storage.repositories.assets_repo import AssetsRepository
from storage.files import compute_checksum
from domain.enums import AssetType
from services import rss as rss_service
from workers.base_worker import BaseWorker
from app.config import config
from app.logging import get_logger

logger = get_logger(__name__)


class FetchWorker(BaseWorker):
    """
    FETCH stage worker.
    Parses RSS feed, downloads audio and cover art, registers assets.
    Params expected in job metadata_json:
        feed_url: str
        episode_number: int
        season: int | None
    """

    def __init__(self, job: Job, jobs_repo: JobsRepository,
                 episodes_repo: EpisodesRepository, assets_repo: AssetsRepository):
        super().__init__(job, jobs_repo)
        self._episodes_repo = episodes_repo
        self._assets_repo = assets_repo

    def run_stage(self) -> None:
        import json
        params = json.loads(self._job.metadata_json or "{}")
        feed_url = params.get("feed_url")
        episode_number = int(params.get("episode_number", 1))
        season = params.get("season")

        if not feed_url:
            raise ValueError("FetchWorker requires feed_url in job metadata_json")

        logger.info({"event": "fetch_start", "feed_url": feed_url})

        # 1. Fetch and match episode from RSS
        feed = rss_service.fetch_feed(feed_url)
        match = rss_service.match_episode(feed, episode_number, season)

        # 2. Update episode record with metadata
        episode_dir = config.output_dir / self._job.episode_id
        episode_dir.mkdir(parents=True, exist_ok=True)

        # 3. Download audio
        audio_path = episode_dir / "audio.mp3"
        rss_service.download_audio(match.audio_url, audio_path)
        checksum = compute_checksum(audio_path)
        self._assets_repo.register(
            self._job.episode_id, AssetType.AUDIO, str(audio_path), checksum
        )

        # 4. Download cover art
        if match.cover_art_url:
            cover_path = episode_dir / "cover.jpg"
            import httpx
            response = httpx.get(match.cover_art_url, timeout=30, follow_redirects=True)
            cover_path.write_bytes(response.content)
            cover_checksum = compute_checksum(cover_path)
            self._assets_repo.register(
                self._job.episode_id, AssetType.COVER_ART, str(cover_path), cover_checksum
            )

        logger.info({"event": "fetch_complete", "episode_id": self._job.episode_id})