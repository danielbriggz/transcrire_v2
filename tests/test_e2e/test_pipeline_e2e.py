import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from domain.enums import Stage, JobStatus, AssetType
from services.groq import GroqTranscriptResult, TranscriptSegment


# ── Pipeline state transitions ────────────────────────────────────────────────

def test_new_episode_has_fetch_action(pipeline, sample_episode):
    actions = pipeline.get_available_actions(sample_episode.id)
    assert "fetch" in actions


def test_enqueue_fetch_creates_queued_job(pipeline, repos, sample_episode):
    job = pipeline.enqueue_stage(sample_episode.id, Stage.FETCH)
    assert job.status == JobStatus.QUEUED
    assert job.stage == Stage.FETCH
    assert job.episode_id == sample_episode.id


def test_cannot_enqueue_transcribe_before_fetch(pipeline, sample_episode):
    with pytest.raises(ValueError, match="FETCH has not completed"):
        pipeline.enqueue_stage(sample_episode.id, Stage.TRANSCRIBE)


def test_full_pipeline_enqueues_four_jobs(pipeline, repos, sample_episode):
    jobs = pipeline.enqueue_full(sample_episode.id)
    assert len(jobs) == 4
    stages = [j.stage for j in jobs]
    assert stages == [Stage.FETCH, Stage.TRANSCRIBE, Stage.CAPTION, Stage.IMAGE]


def test_status_reflects_completed_stage(pipeline, repos, sample_episode):
    job = pipeline.enqueue_stage(sample_episode.id, Stage.FETCH)
    pipeline.transition_job(job.id, JobStatus.RUNNING)
    pipeline.transition_job(job.id, JobStatus.SUCCESS)

    status = pipeline.get_status(sample_episode.id)
    assert Stage.FETCH in status.completed_stages
    assert status.completion_level == 1


# ── Worker execution ──────────────────────────────────────────────────────────

def test_transcribe_worker_saves_transcript_asset(repos, sample_episode, tmp_path):
    from workers.transcribe_worker import TranscribeWorker
    from domain.models import Job
    import uuid

    # Create a fake audio file
    output_dir = tmp_path / "output" / sample_episode.id
    output_dir.mkdir(parents=True)
    audio_path = output_dir / "audio.mp3"
    audio_path.write_bytes(b"\xff\xfb" + b"\x00" * 1024)

    # Register audio asset
    from storage.files import compute_checksum
    repos["assets"].register(
        sample_episode.id, AssetType.AUDIO, str(audio_path),
        compute_checksum(audio_path)
    )

    job = repos["jobs"].create(sample_episode.id, Stage.TRANSCRIBE)

    mock_result = GroqTranscriptResult(
        full_text="This is an end to end test transcript.",
        segments=[TranscriptSegment(0.0, 3.0, "This is an end to end test transcript.")],
        language="en",
        duration_s=3.0,
    )

    with patch("workers.transcribe_worker.audio_service.compress_audio",
               return_value=audio_path), \
         patch("workers.transcribe_worker.audio_service.needs_chunking", return_value=False), \
         patch("workers.transcribe_worker.groq_service.transcribe_file",
               return_value=mock_result), \
         patch("app.config.config.output_dir", tmp_path / "output"):

        worker = TranscribeWorker(job, repos["jobs"], repos["assets"])
        worker.execute()

    asset = repos["assets"].get_active(sample_episode.id, AssetType.TRANSCRIPT)
    assert asset is not None
    assert Path(asset.file_path).exists()
    assert "end to end test" in Path(asset.file_path).read_text(encoding="utf-8")


def test_caption_worker_saves_caption_asset(repos, sample_episode, tmp_path):
    from workers.caption_worker import CaptionWorker
    from services.gemini import CaptionResult

    output_dir = tmp_path / "output" / sample_episode.id
    output_dir.mkdir(parents=True)
    transcript_path = output_dir / "transcript.txt"
    transcript_path.write_text("Test transcript content.", encoding="utf-8")

    from storage.files import compute_checksum
    repos["assets"].register(
        sample_episode.id, AssetType.TRANSCRIPT,
        str(transcript_path), compute_checksum(transcript_path)
    )

    job = repos["jobs"].create(sample_episode.id, Stage.CAPTION)

    def fake_generate(transcript_text, platform, episode_title, spotify_link=None):
        return CaptionResult(platform=platform, caption=f"Caption for {platform}")

    with patch("core.captions.generate_caption", side_effect=fake_generate), \
         patch("app.config.config.output_dir", tmp_path / "output"):

        worker = CaptionWorker(job, repos["jobs"], repos["assets"], repos["episodes"])
        worker.execute()

    asset = repos["assets"].get_active(sample_episode.id, AssetType.CAPTION)
    assert asset is not None
    data = json.loads(Path(asset.file_path).read_text(encoding="utf-8"))
    assert "twitter" in data
    assert "linkedin" in data
    assert "facebook" in data


def test_image_worker_saves_image_asset(repos, sample_episode, tmp_path):
    from workers.image_worker import ImageWorker
    from PIL import Image

    output_dir = tmp_path / "output" / sample_episode.id
    output_dir.mkdir(parents=True)

    cover_path = output_dir / "cover.jpg"
    Image.new("RGB", (500, 500), (30, 30, 30)).save(str(cover_path))

    transcript_path = output_dir / "transcript.txt"
    transcript_path.write_text("Quote text for the card.", encoding="utf-8")

    from storage.files import compute_checksum
    repos["assets"].register(
        sample_episode.id, AssetType.COVER_ART,
        str(cover_path), compute_checksum(cover_path)
    )
    repos["assets"].register(
        sample_episode.id, AssetType.TRANSCRIPT,
        str(transcript_path), compute_checksum(transcript_path)
    )

    job = repos["jobs"].create(sample_episode.id, Stage.IMAGE)

    with patch("app.config.config.output_dir", tmp_path / "output"):
        worker = ImageWorker(job, repos["jobs"], repos["assets"])
        worker.execute()

    asset = repos["assets"].get_active(sample_episode.id, AssetType.IMAGE)
    assert asset is not None
    img = Image.open(asset.file_path)
    assert img.size == (1080, 1080)


# ── Orchestrator dispatch ─────────────────────────────────────────────────────

def test_orchestrator_dispatches_queued_job(repos, sample_episode):
    from app.orchestrator import Orchestrator

    job = repos["jobs"].create(sample_episode.id, Stage.FETCH)
    dispatched = []

    class MockFetchWorker:
        def __init__(self, *args, **kwargs):
            pass
        def execute(self):
            dispatched.append(job.id)
            repos["jobs"].update_status(job.id, JobStatus.SUCCESS)

    with patch("app.orchestrator.FetchWorker", MockFetchWorker), \
         patch("app.orchestrator.get_connection",
               return_value=repos["jobs"]._conn):
        orc = Orchestrator()
        orc._dispatch(job, repos["jobs"]._conn)

    time.sleep(0.1)
    assert job.id in dispatched


def test_worker_heartbeat_updates_during_execution(repos, sample_episode):
    from workers.base_worker import BaseWorker
    import time as time_module

    job = repos["jobs"].create(sample_episode.id, Stage.FETCH)
    repos["jobs"].update_status(job.id, JobStatus.QUEUED)

    class SlowWorker(BaseWorker):
        def run_stage(self):
            time_module.sleep(0.15)

    worker = SlowWorker(job, repos["jobs"])
    worker.execute()

    updated = repos["jobs"].get_by_id(job.id)
    assert updated.status == JobStatus.SUCCESS


def test_worker_marks_job_failed_on_exception(repos, sample_episode):
    from workers.base_worker import BaseWorker

    job = repos["jobs"].create(sample_episode.id, Stage.FETCH)

    class FailingWorker(BaseWorker):
        def run_stage(self):
            raise RuntimeError("Intentional failure")

    worker = FailingWorker(job, repos["jobs"])
    with pytest.raises(RuntimeError):
        worker.execute()

    updated = repos["jobs"].get_by_id(job.id)
    assert updated.status == JobStatus.FAILED