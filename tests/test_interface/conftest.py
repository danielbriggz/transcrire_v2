import pytest
from unittest.mock import MagicMock
from domain.enums import Stage, JobStatus
from domain.models import Job


@pytest.fixture
def mock_pipeline():
    """A fully mocked Pipeline instance for CLI and GUI tests."""
    pipeline = MagicMock()
    pipeline.get_status.return_value = MagicMock(
        completion_level=0,
        completed_stages=[],
        pending_stages=[Stage.FETCH, Stage.TRANSCRIBE, Stage.CAPTION, Stage.IMAGE],
        active_job=None,
        available_actions=["fetch"],
    )
    return pipeline


@pytest.fixture
def mock_episode():
    """A minimal Episode-like mock."""
    ep = MagicMock()
    ep.id = "ep-test-001"
    ep.title = "Test Episode"
    ep.published_date = "2024-01-01"
    return ep


@pytest.fixture
def mock_job():
    return Job(
        id="job-001",
        episode_id="ep-test-001",
        stage=Stage.FETCH,
        status=JobStatus.QUEUED,
        attempt_count=0,
    )