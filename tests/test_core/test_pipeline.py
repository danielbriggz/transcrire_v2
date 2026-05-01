import pytest
from unittest.mock import MagicMock
from domain.enums import Stage, JobStatus
from domain.models import Job
from core.pipeline import Pipeline, PipelineStatus, STAGE_ORDER


@pytest.fixture
def mock_jobs_repo():
    return MagicMock()


@pytest.fixture
def mock_episodes_repo():
    return MagicMock()


@pytest.fixture
def mock_assets_repo():
    return MagicMock()


@pytest.fixture
def pipeline(mock_jobs_repo, mock_episodes_repo, mock_assets_repo):
    return Pipeline(
        jobs_repo=mock_jobs_repo,
        episodes_repo=mock_episodes_repo,
        assets_repo=mock_assets_repo,
    )


def _make_job(stage: Stage, status: JobStatus, job_id: str = "job-1") -> Job:
    return Job(
        id=job_id,
        episode_id="ep-1",
        stage=stage,
        status=status,
        attempt_count=0,
    )


# ── enqueue_stage ─────────────────────────────────────────────────────────────

def test_enqueue_fetch_with_no_prerequisites(pipeline, mock_jobs_repo):
    mock_jobs_repo.get_jobs_for_episode.return_value = []
    mock_jobs_repo.create.return_value = _make_job(Stage.FETCH, JobStatus.QUEUED)

    job = pipeline.enqueue_stage("ep-1", Stage.FETCH)
    assert job.stage == Stage.FETCH
    mock_jobs_repo.create.assert_called_once()


def test_enqueue_transcribe_fails_without_fetch(pipeline, mock_jobs_repo):
    mock_jobs_repo.get_jobs_for_episode.return_value = []

    with pytest.raises(ValueError, match="FETCH has not completed"):
        pipeline.enqueue_stage("ep-1", Stage.TRANSCRIBE)


def test_enqueue_transcribe_succeeds_after_fetch(pipeline, mock_jobs_repo):
    mock_jobs_repo.get_jobs_for_episode.return_value = [
        _make_job(Stage.FETCH, JobStatus.SUCCESS)
    ]
    mock_jobs_repo.create.return_value = _make_job(Stage.TRANSCRIBE, JobStatus.QUEUED)

    job = pipeline.enqueue_stage("ep-1", Stage.TRANSCRIBE)
    assert job.stage == Stage.TRANSCRIBE


def test_enqueue_caption_fails_without_transcribe(pipeline, mock_jobs_repo):
    mock_jobs_repo.get_jobs_for_episode.return_value = [
        _make_job(Stage.FETCH, JobStatus.SUCCESS)
    ]
    with pytest.raises(ValueError, match="TRANSCRIBE has not completed"):
        pipeline.enqueue_stage("ep-1", Stage.CAPTION)


def test_enqueue_image_requires_all_prior_stages(pipeline, mock_jobs_repo):
    mock_jobs_repo.get_jobs_for_episode.return_value = [
        _make_job(Stage.FETCH, JobStatus.SUCCESS),
        _make_job(Stage.TRANSCRIBE, JobStatus.SUCCESS),
    ]
    with pytest.raises(ValueError, match="CAPTION has not completed"):
        pipeline.enqueue_stage("ep-1", Stage.IMAGE)


# ── enqueue_full ──────────────────────────────────────────────────────────────

def test_enqueue_full_creates_four_jobs(pipeline, mock_jobs_repo):
    mock_jobs_repo.create.side_effect = [
        _make_job(Stage.FETCH,      JobStatus.QUEUED, "j1"),
        _make_job(Stage.TRANSCRIBE, JobStatus.QUEUED, "j2"),
        _make_job(Stage.CAPTION,    JobStatus.QUEUED, "j3"),
        _make_job(Stage.IMAGE,      JobStatus.QUEUED, "j4"),
    ]
    jobs = pipeline.enqueue_full("ep-1")
    assert len(jobs) == 4
    assert mock_jobs_repo.create.call_count == 4


def test_enqueue_full_stages_are_in_order(pipeline, mock_jobs_repo):
    stages = list(STAGE_ORDER)
    mock_jobs_repo.create.side_effect = [
        _make_job(s, JobStatus.QUEUED, f"j{i}") for i, s in enumerate(stages)
    ]
    jobs = pipeline.enqueue_full("ep-1")
    assert [j.stage for j in jobs] == stages


# ── transition_job ────────────────────────────────────────────────────────────

def test_transition_job_valid(pipeline, mock_jobs_repo):
    job = _make_job(Stage.FETCH, JobStatus.QUEUED)
    updated = _make_job(Stage.FETCH, JobStatus.RUNNING)
    mock_jobs_repo.get_by_id.side_effect = [job, updated]

    result = pipeline.transition_job("job-1", JobStatus.RUNNING)
    assert result.status == JobStatus.RUNNING
    mock_jobs_repo.update_status.assert_called_once_with("job-1", JobStatus.RUNNING)


def test_transition_job_invalid_raises(pipeline, mock_jobs_repo):
    job = _make_job(Stage.FETCH, JobStatus.SUCCESS)
    mock_jobs_repo.get_by_id.return_value = job

    with pytest.raises(ValueError, match="Invalid transition"):
        pipeline.transition_job("job-1", JobStatus.RUNNING)


def test_transition_job_not_found_raises(pipeline, mock_jobs_repo):
    mock_jobs_repo.get_by_id.return_value = None

    with pytest.raises(ValueError, match="Job not found"):
        pipeline.transition_job("nonexistent", JobStatus.RUNNING)


# ── get_status ────────────────────────────────────────────────────────────────

def test_get_status_new_episode_has_zero_completion(pipeline, mock_jobs_repo):
    mock_jobs_repo.get_jobs_for_episode.return_value = []
    status = pipeline.get_status("ep-1")

    assert status.completion_level == 0
    assert status.completed_stages == []
    assert status.pending_stages == STAGE_ORDER
    assert status.active_job is None


def test_get_status_after_fetch_complete(pipeline, mock_jobs_repo):
    mock_jobs_repo.get_jobs_for_episode.return_value = [
        _make_job(Stage.FETCH, JobStatus.SUCCESS)
    ]
    status = pipeline.get_status("ep-1")

    assert status.completion_level == 1
    assert Stage.FETCH in status.completed_stages
    assert Stage.TRANSCRIBE in status.pending_stages


def test_get_status_all_complete(pipeline, mock_jobs_repo):
    mock_jobs_repo.get_jobs_for_episode.return_value = [
        _make_job(Stage.FETCH,      JobStatus.SUCCESS, "j1"),
        _make_job(Stage.TRANSCRIBE, JobStatus.SUCCESS, "j2"),
        _make_job(Stage.CAPTION,    JobStatus.SUCCESS, "j3"),
        _make_job(Stage.IMAGE,      JobStatus.SUCCESS, "j4"),
    ]
    status = pipeline.get_status("ep-1")

    assert status.completion_level == 4
    assert status.pending_stages == []


def test_get_status_detects_active_job(pipeline, mock_jobs_repo):
    running_job = _make_job(Stage.TRANSCRIBE, JobStatus.RUNNING)
    mock_jobs_repo.get_jobs_for_episode.return_value = [
        _make_job(Stage.FETCH, JobStatus.SUCCESS),
        running_job,
    ]
    status = pipeline.get_status("ep-1")
    assert status.active_job is not None
    assert status.active_job.status == JobStatus.RUNNING


# ── get_available_actions ─────────────────────────────────────────────────────

def test_actions_new_episode_returns_fetch(pipeline, mock_jobs_repo):
    mock_jobs_repo.get_jobs_for_episode.return_value = []
    actions = pipeline.get_available_actions("ep-1")
    assert actions == ["fetch"]


def test_actions_after_fetch_includes_transcribe(pipeline, mock_jobs_repo):
    mock_jobs_repo.get_jobs_for_episode.return_value = [
        _make_job(Stage.FETCH, JobStatus.SUCCESS)
    ]
    actions = pipeline.get_available_actions("ep-1")
    assert "transcribe" in actions
    assert "re_fetch" in actions


def test_actions_during_active_job_returns_view_progress(pipeline, mock_jobs_repo):
    mock_jobs_repo.get_jobs_for_episode.return_value = [
        _make_job(Stage.FETCH,      JobStatus.SUCCESS),
        _make_job(Stage.TRANSCRIBE, JobStatus.RUNNING),
    ]
    actions = pipeline.get_available_actions("ep-1")
    assert actions == ["view_progress"]


def test_actions_all_complete_includes_run_full_pipeline(pipeline, mock_jobs_repo):
    mock_jobs_repo.get_jobs_for_episode.return_value = [
        _make_job(Stage.FETCH,      JobStatus.SUCCESS, "j1"),
        _make_job(Stage.TRANSCRIBE, JobStatus.SUCCESS, "j2"),
        _make_job(Stage.CAPTION,    JobStatus.SUCCESS, "j3"),
        _make_job(Stage.IMAGE,      JobStatus.SUCCESS, "j4"),
    ]
    actions = pipeline.get_available_actions("ep-1")
    assert "run_full_pipeline" in actions
    assert "regenerate_image" in actions