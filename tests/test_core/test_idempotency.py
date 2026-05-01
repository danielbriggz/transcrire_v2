import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from domain.enums import AssetType
from core.idempotency import should_skip_stage, compute_params_fingerprint


@pytest.fixture
def mock_assets_repo():
    return MagicMock()


@pytest.fixture
def real_file(tmp_path):
    """A real file with known content for checksum testing."""
    f = tmp_path / "transcript.txt"
    f.write_text("hello world", encoding="utf-8")
    return f


# ── Skip logic ────────────────────────────────────────────────────────────────

def test_skips_when_asset_exists_and_checksum_matches(mock_assets_repo, real_file):
    from storage.files import compute_checksum
    real_checksum = compute_checksum(real_file)

    mock_assets_repo.get_active.return_value = MagicMock(
        file_path=str(real_file),
        checksum=real_checksum,
    )
    result = should_skip_stage("ep-1", AssetType.TRANSCRIPT, mock_assets_repo)
    assert result is True


def test_does_not_skip_when_no_asset(mock_assets_repo):
    mock_assets_repo.get_active.return_value = None
    result = should_skip_stage("ep-1", AssetType.TRANSCRIPT, mock_assets_repo)
    assert result is False


def test_does_not_skip_when_file_missing(mock_assets_repo, tmp_path):
    mock_assets_repo.get_active.return_value = MagicMock(
        file_path=str(tmp_path / "nonexistent.txt"),
        checksum="abc123",
    )
    result = should_skip_stage("ep-1", AssetType.TRANSCRIPT, mock_assets_repo)
    assert result is False


def test_does_not_skip_when_checksum_mismatch(mock_assets_repo, real_file):
    mock_assets_repo.get_active.return_value = MagicMock(
        file_path=str(real_file),
        checksum="completely_wrong_checksum",
    )
    result = should_skip_stage("ep-1", AssetType.TRANSCRIPT, mock_assets_repo)
    assert result is False


def test_uses_provided_path_over_db_path(mock_assets_repo, real_file, tmp_path):
    """If current_file_path is explicitly passed, it is used instead of asset.file_path."""
    from storage.files import compute_checksum
    real_checksum = compute_checksum(real_file)

    mock_assets_repo.get_active.return_value = MagicMock(
        file_path=str(tmp_path / "different_path.txt"),  # different path in DB
        checksum=real_checksum,
    )
    # Pass the real file explicitly — should match and skip
    result = should_skip_stage(
        "ep-1", AssetType.TRANSCRIPT, mock_assets_repo,
        current_file_path=real_file
    )
    assert result is True


def test_different_asset_types_checked_independently(mock_assets_repo):
    mock_assets_repo.get_active.return_value = None
    assert should_skip_stage("ep-1", AssetType.AUDIO, mock_assets_repo) is False
    assert should_skip_stage("ep-1", AssetType.IMAGE, mock_assets_repo) is False


# ── Params fingerprint ────────────────────────────────────────────────────────

def test_fingerprint_is_deterministic():
    params = {"model": "whisper-large-v3", "language": "en"}
    assert compute_params_fingerprint(params) == compute_params_fingerprint(params)


def test_fingerprint_differs_for_different_params():
    params_a = {"model": "base", "language": "en"}
    params_b = {"model": "large", "language": "en"}
    assert compute_params_fingerprint(params_a) != compute_params_fingerprint(params_b)


def test_fingerprint_is_key_order_independent():
    params_a = {"language": "en", "model": "base"}
    params_b = {"model": "base", "language": "en"}
    assert compute_params_fingerprint(params_a) == compute_params_fingerprint(params_b)


def test_fingerprint_returns_string():
    result = compute_params_fingerprint({"key": "value"})
    assert isinstance(result, str)
    assert len(result) == 64  # SHA-256 hex digest is always 64 chars