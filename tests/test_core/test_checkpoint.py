import pytest
import json
from unittest.mock import MagicMock
from core.checkpoint import Checkpoint


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def checkpoint(mock_repo):
    return Checkpoint(job_id="test-job-123", jobs_repo=mock_repo)


# ── Save ──────────────────────────────────────────────────────────────────────

def test_save_calls_set_metadata(checkpoint, mock_repo):
    data = {"last_chunk_index": 2, "time_offset": 120.0}
    checkpoint.save(data)
    mock_repo.set_metadata.assert_called_once_with("test-job-123", data)


# ── Load ──────────────────────────────────────────────────────────────────────

def test_load_returns_dict_when_metadata_exists(checkpoint, mock_repo):
    mock_repo.get_by_id.return_value = MagicMock(
        metadata_json='{"last_chunk_index": 2, "time_offset": 120.0}'
    )
    result = checkpoint.load()
    assert result == {"last_chunk_index": 2, "time_offset": 120.0}


def test_load_returns_none_when_no_job(checkpoint, mock_repo):
    mock_repo.get_by_id.return_value = None
    assert checkpoint.load() is None


def test_load_returns_none_when_metadata_is_empty_string(checkpoint, mock_repo):
    mock_repo.get_by_id.return_value = MagicMock(metadata_json="")
    assert checkpoint.load() is None


def test_load_returns_none_when_metadata_is_none(checkpoint, mock_repo):
    mock_repo.get_by_id.return_value = MagicMock(metadata_json=None)
    assert checkpoint.load() is None


def test_load_returns_none_on_corrupt_json(checkpoint, mock_repo):
    mock_repo.get_by_id.return_value = MagicMock(metadata_json="{not valid json")
    assert checkpoint.load() is None


def test_load_handles_dict_metadata_directly(checkpoint, mock_repo):
    """Metadata already parsed as dict (not a string) should still return correctly."""
    mock_repo.get_by_id.return_value = MagicMock(
        metadata_json={"last_chunk_index": 1}
    )
    result = checkpoint.load()
    assert result == {"last_chunk_index": 1}


# ── Clear ─────────────────────────────────────────────────────────────────────

def test_clear_calls_set_metadata_with_empty_dict(checkpoint, mock_repo):
    checkpoint.clear()
    mock_repo.set_metadata.assert_called_once_with("test-job-123", {})


# ── Round-trip ────────────────────────────────────────────────────────────────

def test_save_then_load_round_trip(mock_repo):
    """Simulate a full save → load cycle."""
    stored = {}

    def fake_set_metadata(job_id, data):
        stored["metadata_json"] = json.dumps(data)

    def fake_get_by_id(job_id):
        return MagicMock(metadata_json=stored.get("metadata_json"))

    mock_repo.set_metadata.side_effect = fake_set_metadata
    mock_repo.get_by_id.side_effect = fake_get_by_id

    cp = Checkpoint(job_id="round-trip-job", jobs_repo=mock_repo)
    cp.save({"last_chunk_index": 4, "time_offset": 240.0})
    result = cp.load()

    assert result["last_chunk_index"] == 4
    assert result["time_offset"] == 240.0