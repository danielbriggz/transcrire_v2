import json
from pathlib import Path
from domain.models import Job
from storage.repositories.jobs_repo import JobsRepository
from storage.repositories.assets_repo import AssetsRepository
from storage.files import compute_checksum
from core.checkpoint import Checkpoint
from core.idempotency import should_skip_stage
from core.transcript import build_formatted_transcript
from domain.enums import AssetType, TranscribeMode
from services import audio as audio_service
from services import groq as groq_service
from services import whisper as whisper_service
from workers.base_worker import BaseWorker
from app.config import config
from app.logging import get_logger

logger = get_logger(__name__)


class TranscribeWorker(BaseWorker):
    """
    TRANSCRIBE stage worker.
    Compresses audio, chunks if needed, transcribes via Groq or Whisper,
    saves plain and timestamped transcript files.
    Params in job metadata_json:
        mode: "CLOUD" | "LOCAL"  (default: CLOUD)
    """

    def __init__(self, job: Job, jobs_repo: JobsRepository, assets_repo: AssetsRepository):
        super().__init__(job, jobs_repo)
        self._assets_repo = assets_repo

    def run_stage(self) -> None:
        params = json.loads(self._job.metadata_json or "{}")
        mode = TranscribeMode(params.get("mode", "CLOUD"))

        # Idempotency check
        if should_skip_stage(self._job.episode_id, AssetType.TRANSCRIPT, self._assets_repo):
            logger.info({"event": "transcribe_skipped_idempotent", "episode_id": self._job.episode_id})
            return

        # Load audio asset
        audio_asset = self._assets_repo.get_active(self._job.episode_id, AssetType.AUDIO)
        if not audio_asset:
            raise ValueError("No audio asset found. Run FETCH stage first.")

        audio_path = Path(audio_asset.file_path)
        episode_dir = config.output_dir / self._job.episode_id
        checkpoint = Checkpoint(self._job.id, self._jobs_repo)

        # Compress audio before sending to Groq
        compressed_path = episode_dir / "audio_compressed.mp3"
        audio_service.compress_audio(audio_path, compressed_path)

        # Transcribe
        if mode == TranscribeMode.CLOUD:
            if audio_service.needs_chunking(compressed_path):
                chunks_dir = episode_dir / "chunks"
                chunks = audio_service.split_into_chunks(compressed_path, chunks_dir)
                result = groq_service.transcribe_chunks(
                    chunks,
                    checkpoint_save_fn=lambda i, segs, offset: checkpoint.save({
                        "last_chunk_index": i, "segments": segs, "time_offset": offset
                    }),
                    checkpoint_load_fn=checkpoint.load,
                )
            else:
                result = groq_service.transcribe_file(compressed_path)
        else:
            result = whisper_service.transcribe_file(compressed_path)

        # Format and save transcript
        formatted = build_formatted_transcript(result.segments, result.duration_s)
        plain_path = episode_dir / "transcript.txt"
        timestamped_path = episode_dir / "transcript_timestamped.txt"

        plain_path.write_text(formatted.plain_text, encoding="utf-8")
        timestamped_path.write_text(formatted.segment_text, encoding="utf-8")

        checksum = compute_checksum(plain_path)
        self._assets_repo.register(
            self._job.episode_id, AssetType.TRANSCRIPT, str(plain_path), checksum
        )

        checkpoint.clear()
        logger.info({
            "event": "transcribe_complete",
            "episode_id": self._job.episode_id,
            "word_count": formatted.word_count,
        })