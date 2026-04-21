-- ============================================================
-- Transcrire Database Schema
-- All statements use IF NOT EXISTS — safe to run on startup.
-- ============================================================

-- ------------------------------------------------------------
-- 1. EPISODES
-- Core registry of all known podcast episodes.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS episodes (
    id              TEXT PRIMARY KEY,           -- UUID
    title           TEXT NOT NULL,
    published_date  TEXT,                       -- ISO 8601 date string
    feed_url        TEXT,
    spotify_link    TEXT,
    status          TEXT NOT NULL DEFAULT 'NEW',
    created_at      TEXT NOT NULL               -- ISO 8601 datetime
);

-- ------------------------------------------------------------
-- 2. JOBS
-- Execution units — one row per stage attempt per episode.
-- This is the heartbeat of the production pipeline.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jobs (
    id              TEXT PRIMARY KEY,           -- UUID
    episode_id      TEXT NOT NULL,
    stage           TEXT NOT NULL,              -- Stage enum value
    status          TEXT NOT NULL DEFAULT 'QUEUED',
    attempt_count   INTEGER NOT NULL DEFAULT 0,
    execution_id    TEXT,                       -- UUID per attempt
    worker_id       TEXT,
    started_at      TEXT,
    updated_at      TEXT,
    heartbeat_at    TEXT,                       -- Updated every ~5s by worker
    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_episode_id ON jobs(episode_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_heartbeat ON jobs(heartbeat_at);

-- ------------------------------------------------------------
-- 3. STAGE RESULTS
-- Immutable log of completed stage executions.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stage_results (
    id              TEXT PRIMARY KEY,           -- UUID
    job_id          TEXT NOT NULL,
    episode_id      TEXT NOT NULL,
    stage           TEXT NOT NULL,
    status          TEXT NOT NULL,
    duration_ms     INTEGER,
    metadata_json   TEXT,                       -- JSON string
    error_log       TEXT,
    created_at      TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);

CREATE INDEX IF NOT EXISTS idx_stage_results_episode ON stage_results(episode_id);
CREATE INDEX IF NOT EXISTS idx_stage_results_job ON stage_results(job_id);

-- ------------------------------------------------------------
-- 4. ASSETS
-- Tracks every file produced by the pipeline with versioning
-- and checksum-based integrity detection.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assets (
    id              TEXT PRIMARY KEY,           -- UUID
    episode_id      TEXT NOT NULL,
    asset_type      TEXT NOT NULL,              -- AssetType enum value
    file_path       TEXT NOT NULL,
    checksum        TEXT NOT NULL,              -- SHA-256 hex digest
    version         INTEGER NOT NULL DEFAULT 1,
    is_active       INTEGER NOT NULL DEFAULT 1, -- Boolean (1/0)
    created_at      TEXT NOT NULL,
    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);

CREATE INDEX IF NOT EXISTS idx_assets_episode ON assets(episode_id);
CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);

-- Enforce one active asset per type per episode
CREATE UNIQUE INDEX IF NOT EXISTS idx_assets_active_unique
    ON assets(episode_id, asset_type)
    WHERE is_active = 1;

-- ------------------------------------------------------------
-- 5. EVENTS
-- Append-only durable event log. Never updated, only inserted.
-- Replayed on startup if the in-memory emitter missed events.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id              TEXT PRIMARY KEY,           -- UUID
    job_id          TEXT NOT NULL,
    episode_id      TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    payload_json    TEXT,                       -- JSON string
    created_at      TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (episode_id) REFERENCES episodes(id)
);

CREATE INDEX IF NOT EXISTS idx_events_job ON events(job_id);
CREATE INDEX IF NOT EXISTS idx_events_episode ON events(episode_id);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);