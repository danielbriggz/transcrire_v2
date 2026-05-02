import pytest
from unittest.mock import MagicMock, patch


# ── tasks.py ─────────────────────────────────────────────────────────────────

def test_run_stage_in_background_sets_task_state():
    import time
    from interface.gui.tasks import run_stage_in_background, get_task_state, _active_tasks

    _active_tasks.clear()
    completed = {"done": False}

    def fake_worker():
        time.sleep(0.05)

    def on_complete():
        completed["done"] = True

    state = run_stage_in_background(
        task_id="task-001",
        episode_id="ep-001",
        stage="FETCH",
        worker_fn=fake_worker,
        on_complete=on_complete,
    )

    assert state.task_id == "task-001"
    assert state.episode_id == "ep-001"
    assert state.stage == "FETCH"
    assert state.is_complete is False

    time.sleep(0.2)
    assert completed["done"] is True


def test_run_stage_in_background_captures_error():
    import time
    from interface.gui.tasks import run_stage_in_background, _active_tasks

    _active_tasks.clear()
    errors = []

    def failing_worker():
        raise RuntimeError("Something went wrong")

    run_stage_in_background(
        task_id="task-fail",
        episode_id="ep-002",
        stage="TRANSCRIBE",
        worker_fn=failing_worker,
        on_error=lambda e: errors.append(str(e)),
    )

    time.sleep(0.2)
    assert len(errors) == 1
    assert "Something went wrong" in errors[0]


def test_is_task_running_true_during_execution():
    import time
    from interface.gui.tasks import run_stage_in_background, is_task_running, _active_tasks

    _active_tasks.clear()

    def slow_worker():
        time.sleep(0.3)

    run_stage_in_background(
        task_id="task-running",
        episode_id="ep-running",
        stage="IMAGE",
        worker_fn=slow_worker,
    )

    time.sleep(0.05)
    assert is_task_running("ep-running") is True

    time.sleep(0.4)
    assert is_task_running("ep-running") is False


def test_is_task_running_false_for_unknown_episode():
    from interface.gui.tasks import is_task_running
    assert is_task_running("ep-nonexistent") is False


# ── websocket.py ──────────────────────────────────────────────────────────────

def test_register_and_unregister_listener():
    from interface.gui.websocket import (
        register_progress_listener,
        unregister_progress_listener,
        _client_listeners,
    )

    received = []
    register_progress_listener("client-001", lambda data: received.append(data))
    assert "client-001" in _client_listeners

    unregister_progress_listener("client-001")
    assert "client-001" not in _client_listeners


def test_event_emitter_triggers_listener():
    import time
    from interface.gui.websocket import register_progress_listener, unregister_progress_listener
    from events.emitter import emitter

    received = []
    register_progress_listener("client-002", lambda data: received.append(data))

    emitter.emit("stage_started", {"episode_id": "ep-ws-test", "stage": "FETCH"})
    time.sleep(0.05)

    assert any(d.get("event_type") == "stage_started" for d in received)
    unregister_progress_listener("client-002")


def test_listener_receives_correct_event_types():
    from interface.gui.websocket import register_progress_listener, unregister_progress_listener
    from events.emitter import emitter

    received_types = []
    register_progress_listener(
        "client-003",
        lambda data: received_types.append(data.get("event_type"))
    )

    emitter.emit("stage_completed", {"episode_id": "ep-003", "stage": "TRANSCRIBE"})
    emitter.emit("stage_failed", {"episode_id": "ep-003", "error": "timeout"})

    import time
    time.sleep(0.05)

    assert "stage_completed" in received_types
    assert "stage_failed" in received_types
    unregister_progress_listener("client-003")


# ── lifecycle.py ──────────────────────────────────────────────────────────────

def test_startup_runs_migrations_and_stale_recovery():
    with patch("app.lifecycle.get_connection") as mock_conn, \
         patch("app.lifecycle.run_migrations") as mock_migrate, \
         patch("app.lifecycle.JobsRepository") as mock_repo_cls:

        mock_repo_cls.return_value.mark_stale_jobs.return_value = []
        from app.lifecycle import startup
        startup()

        mock_migrate.assert_called_once()
        mock_repo_cls.return_value.mark_stale_jobs.assert_called_once()


def test_startup_logs_stale_jobs_when_found():
    with patch("app.lifecycle.get_connection"), \
         patch("app.lifecycle.run_migrations"), \
         patch("app.lifecycle.JobsRepository") as mock_repo_cls:

        mock_repo_cls.return_value.mark_stale_jobs.return_value = ["job-a", "job-b"]
        from app.lifecycle import startup
        startup()  # Should not raise — stale jobs are logged, not raised


# ── settings helpers ──────────────────────────────────────────────────────────

def test_save_and_load_keys(tmp_path):
    import json
    from unittest.mock import patch

    config_path = tmp_path / "config.json"

    with patch("interface.gui.pages.settings.CONFIG_PATH", config_path):
        from interface.gui.pages.settings import _save_keys, _load_saved_keys
        _save_keys("groq-test-key", "gemini-test-key")
        loaded = _load_saved_keys()

    assert loaded["GROQ_API_KEY"] == "groq-test-key"
    assert loaded["GEMINI_API_KEY"] == "gemini-test-key"


def test_load_keys_returns_empty_when_no_file(tmp_path):
    missing_path = tmp_path / "nonexistent.json"

    with patch("interface.gui.pages.settings.CONFIG_PATH", missing_path):
        from interface.gui.pages.settings import _load_saved_keys
        result = _load_saved_keys()

    assert result == {}


def test_load_keys_returns_empty_on_corrupt_json(tmp_path):
    bad_file = tmp_path / "config.json"
    bad_file.write_text("{not valid json", encoding="utf-8")

    with patch("interface.gui.pages.settings.CONFIG_PATH", bad_file):
        from interface.gui.pages.settings import _load_saved_keys
        result = _load_saved_keys()

    assert result == {}