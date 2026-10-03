CREATE TABLE IF NOT EXISTS schema_migrations (
  version     TEXT PRIMARY KEY,
  applied_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
  id            TEXT PRIMARY KEY,
  source_url    TEXT NOT NULL,
  video_id      TEXT,
  title         TEXT,
  duration_s    REAL,
  genre         TEXT NOT NULL DEFAULT 'gaming',
  language      TEXT NOT NULL DEFAULT 'id',
  params_json   TEXT NOT NULL,
  status        TEXT NOT NULL,
  stage         TEXT,
  progress      REAL NOT NULL DEFAULT 0,
  error_code    TEXT,
  error_message TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL,
  finished_at   TEXT
);

CREATE TABLE IF NOT EXISTS stage_runs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id      TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  stage       TEXT NOT NULL,
  attempt     INTEGER NOT NULL DEFAULT 1,
  status      TEXT NOT NULL,
  input_hash  TEXT,
  started_at  TEXT NOT NULL,
  finished_at TEXT,
  duration_ms INTEGER,
  metrics_json TEXT,
  error       TEXT
);

CREATE TABLE IF NOT EXISTS events (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id       TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  ts           TEXT NOT NULL,
  type         TEXT NOT NULL,
  payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
  id           TEXT PRIMARY KEY,
  job_id       TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  rank         INTEGER,
  start_s      REAL NOT NULL,
  end_s        REAL NOT NULL,
  peak_s       REAL NOT NULL,
  signal_score REAL NOT NULL,
  llm_score    REAL,
  final_score  REAL NOT NULL,
  category     TEXT,
  title        TEXT,
  hook_text    TEXT,
  reason       TEXT,
  evidence_json TEXT NOT NULL,
  flags_json   TEXT NOT NULL DEFAULT '[]',
  status       TEXT NOT NULL DEFAULT 'proposed',
  user_start_s REAL,
  user_end_s   REAL
);

CREATE TABLE IF NOT EXISTS clips (
  id                 TEXT PRIMARY KEY,
  candidate_id       TEXT NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
  job_id             TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  status             TEXT NOT NULL,
  video_path         TEXT,
  thumb_path         TEXT,
  srt_path           TEXT,
  width              INTEGER,
  height             INTEGER,
  duration_s         REAL,
  render_params_json TEXT NOT NULL,
  qa_json            TEXT,
  created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subtitle_tracks (
  id         TEXT PRIMARY KEY,
  clip_id    TEXT NOT NULL REFERENCES clips(id) ON DELETE CASCADE,
  revision   INTEGER NOT NULL,
  source     TEXT NOT NULL,
  language   TEXT,
  style_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE (clip_id, revision)
);

CREATE TABLE IF NOT EXISTS subtitle_words (
  track_id   TEXT NOT NULL REFERENCES subtitle_tracks(id) ON DELETE CASCADE,
  idx        INTEGER NOT NULL,
  start_s    REAL NOT NULL,
  end_s      REAL NOT NULL,
  text       TEXT NOT NULL,
  confidence REAL,
  PRIMARY KEY (track_id, idx)
);

CREATE TABLE IF NOT EXISTS feedback (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id         TEXT NOT NULL,
  candidate_id   TEXT NOT NULL,
  action         TEXT NOT NULL,
  features_json  TEXT NOT NULL,
  note           TEXT,
  created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS glossary (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  term        TEXT NOT NULL,
  replacement TEXT,
  kind        TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  UNIQUE (term, kind)
);
