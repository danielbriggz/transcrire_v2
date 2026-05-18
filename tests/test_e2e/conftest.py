import pytest
import uuid
from pathlib import Path
from storage.db import get_connection, run_migrations
from storage.repositories.episodes_repo import EpisodesRepository
from storage.repositories.jobs_repo import JobsRepository
from storage.repositories.assets_repo import AssetsRepository
from core.pipeline import Pipeline


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    """Isolated in-memory-style SQLite DB for each test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("TRANSCRIRE_DB_PATH", str(db_path))
    monkeypatch.setenv("TRANSCRIRE_OUTPUT_DIR", str(tmp_path / "output"))

    # Re-import config to pick up monkeypatched env vars
    import importlib
    import app.config
    importlib.reload(app.config)

    conn = get_connection()
    run_migrations(conn)
    return conn


@pytest.fixture
def repos(tmp_db):
    return {
        "episodes": EpisodesRepository(tmp_db),
        "jobs":     JobsRepository(tmp_db),
        "assets":   AssetsRepository(tmp_db),
    }


@pytest.fixture
def pipeline(repos):
    return Pipeline(
        jobs_repo=repos["jobs"],
        episodes_repo=repos["episodes"],
        assets_repo=repos["assets"],
    )


@pytest.fixture
def sample_episode(repos):
    return repos["episodes"].create(
        title="E2E Test Episode",
        published_date="2024-01-01",
        feed_url="https://example.com/feed.rss",
    )