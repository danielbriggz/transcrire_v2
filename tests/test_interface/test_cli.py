import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from domain.enums import Stage, JobStatus
from domain.models import Job
from interface.cli.main import app

runner = CliRunner()


# ── episode list ──────────────────────────────────────────────────────────────

def test_list_no_episodes():
    with patch("interface.cli.commands.EpisodesRepository") as mock_repo_cls, \
         patch("interface.cli.commands.get_connection"), \
         patch("interface.cli.commands.run_migrations"):
        mock_repo_cls.return_value.list_all.return_value = []
        result = runner.invoke(app, ["episode", "list"])

    assert result.exit_code == 0
    assert "No episodes found" in result.output


def test_list_with_episodes(mock_episode, mock_pipeline):
    with patch("interface.cli.commands.EpisodesRepository") as mock_repo_cls, \
         patch("interface.cli.commands.Pipeline", return_value=mock_pipeline), \
         patch("interface.cli.commands.JobsRepository"), \
         patch("interface.cli.commands.AssetsRepository"), \
         patch("interface.cli.commands.get_connection"), \
         patch("interface.cli.commands.run_migrations"):
        mock_repo_cls.return_value.list_all.return_value = [mock_episode]
        result = runner.invoke(app, ["episode", "list"])

    assert result.exit_code == 0
    assert "Test Episode" in result.output


# ── episode status ────────────────────────────────────────────────────────────

def test_status_outputs_completion_level(mock_pipeline):
    mock_pipeline.get_status.return_value = MagicMock(
        completion_level=2,
        completed_stages=[Stage.FETCH, Stage.TRANSCRIBE],
        pending_stages=[Stage.CAPTION, Stage.IMAGE],
        active_job=None,
        available_actions=["generate_captions"],
    )
    with patch("interface.cli.commands.Pipeline", return_value=mock_pipeline), \
         patch("interface.cli.commands.JobsRepository"), \
         patch("interface.cli.commands.EpisodesRepository"), \
         patch("interface.cli.commands.AssetsRepository"), \
         patch("interface.cli.commands.get_connection"), \
         patch("interface.cli.commands.run_migrations"):
        result = runner.invoke(app, ["episode", "status", "ep-001"])

    assert result.exit_code == 0
    assert "2/4" in result.output


def test_status_shows_active_job(mock_pipeline):
    active = MagicMock()
    active.id = "job-active-123"
    mock_pipeline.get_status.return_value = MagicMock(
        completion_level=1,
        completed_stages=[Stage.FETCH],
        pending_stages=[Stage.TRANSCRIBE, Stage.CAPTION, Stage.IMAGE],
        active_job=active,
        available_actions=["view_progress"],
    )
    with patch("interface.cli.commands.Pipeline", return_value=mock_pipeline), \
         patch("interface.cli.commands.JobsRepository"), \
         patch("interface.cli.commands.EpisodesRepository"), \
         patch("interface.cli.commands.AssetsRepository"), \
         patch("interface.cli.commands.get_connection"), \
         patch("interface.cli.commands.run_migrations"):
        result = runner.invoke(app, ["episode", "status", "ep-001"])

    assert "job-active-123" in result.output


# ── episode run ───────────────────────────────────────────────────────────────

def test_run_full_enqueues_four_stages(mock_pipeline, mock_job):
    mock_pipeline.enqueue_full.return_value = [mock_job] * 4

    with patch("interface.cli.commands.Pipeline", return_value=mock_pipeline), \
         patch("interface.cli.commands.JobsRepository"), \
         patch("interface.cli.commands.EpisodesRepository"), \
         patch("interface.cli.commands.AssetsRepository"), \
         patch("interface.cli.commands.get_connection"), \
         patch("interface.cli.commands.run_migrations"):
        result = runner.invoke(app, ["episode", "run", "ep-001", "--full"])

    assert result.exit_code == 0
    assert "4" in result.output
    mock_pipeline.enqueue_full.assert_called_once_with("ep-001")


def test_run_single_stage(mock_pipeline, mock_job):
    mock_pipeline.enqueue_stage.return_value = mock_job

    with patch("interface.cli.commands.Pipeline", return_value=mock_pipeline), \
         patch("interface.cli.commands.JobsRepository"), \
         patch("interface.cli.commands.EpisodesRepository"), \
         patch("interface.cli.commands.AssetsRepository"), \
         patch("interface.cli.commands.get_connection"), \
         patch("interface.cli.commands.run_migrations"):
        result = runner.invoke(app, ["episode", "run", "ep-001", "--stage", "FETCH"])

    assert result.exit_code == 0
    mock_pipeline.enqueue_stage.assert_called_once_with("ep-001", Stage.FETCH)


def test_run_invalid_stage_exits_with_error(mock_pipeline):
    with patch("interface.cli.commands.Pipeline", return_value=mock_pipeline), \
         patch("interface.cli.commands.JobsRepository"), \
         patch("interface.cli.commands.EpisodesRepository"), \
         patch("interface.cli.commands.AssetsRepository"), \
         patch("interface.cli.commands.get_connection"), \
         patch("interface.cli.commands.run_migrations"):
        result = runner.invoke(app, ["episode", "run", "ep-001", "--stage", "INVALID"])

    assert result.exit_code == 1
    assert "Unknown stage" in result.output


def test_run_stage_prerequisite_error_exits(mock_pipeline):
    mock_pipeline.enqueue_stage.side_effect = ValueError("FETCH has not completed successfully.")

    with patch("interface.cli.commands.Pipeline", return_value=mock_pipeline), \
         patch("interface.cli.commands.JobsRepository"), \
         patch("interface.cli.commands.EpisodesRepository"), \
         patch("interface.cli.commands.AssetsRepository"), \
         patch("interface.cli.commands.get_connection"), \
         patch("interface.cli.commands.run_migrations"):
        result = runner.invoke(app, ["episode", "run", "ep-001", "--stage", "TRANSCRIBE"])

    assert result.exit_code == 1
    assert "FETCH has not completed" in result.output


def test_run_no_flags_shows_available_actions(mock_pipeline):
    with patch("interface.cli.commands.Pipeline", return_value=mock_pipeline), \
         patch("interface.cli.commands.JobsRepository"), \
         patch("interface.cli.commands.EpisodesRepository"), \
         patch("interface.cli.commands.AssetsRepository"), \
         patch("interface.cli.commands.get_connection"), \
         patch("interface.cli.commands.run_migrations"):
        result = runner.invoke(app, ["episode", "run", "ep-001"])

    assert result.exit_code == 0
    assert "fetch" in result.output