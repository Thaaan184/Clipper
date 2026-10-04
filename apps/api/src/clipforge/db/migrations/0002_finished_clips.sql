-- Migration 0002: Add finished_clips table for global persistent results

CREATE TABLE IF NOT EXISTS finished_clips (
    id                TEXT PRIMARY KEY,
    clip_id           TEXT NOT NULL,
    job_id            TEXT,
    project_title     TEXT,
    video_path        TEXT NOT NULL,
    thumb_path        TEXT,
    srt_path          TEXT,
    duration_s        REAL,
    width             INTEGER DEFAULT 1080,
    height            INTEGER DEFAULT 1920,
    subtitles_json    TEXT,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_finished_clips_created ON finished_clips(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_finished_clips_clip_id ON finished_clips(clip_id);
