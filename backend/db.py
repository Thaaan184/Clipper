import aiosqlite
from config import settings

DB = str(settings.db_path)

CREATE_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS videos (
    id          TEXT PRIMARY KEY,
    url         TEXT NOT NULL,
    title       TEXT,
    duration    INTEGER,
    thumbnail   TEXT,
    channel     TEXT,
    transcript  TEXT,
    audio_spikes TEXT,
    status      TEXT DEFAULT 'pending',
    error_msg   TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clips (
    id           TEXT PRIMARY KEY,
    video_id     TEXT NOT NULL REFERENCES videos(id),
    clip_index   INTEGER NOT NULL,
    start_time   REAL NOT NULL,
    end_time     REAL NOT NULL,
    duration     REAL,
    hook_title   TEXT,
    score        INTEGER DEFAULT 0,
    reason       TEXT,
    caption      TEXT,
    hashtags     TEXT,
    content_type TEXT DEFAULT 'general',
    layout       TEXT DEFAULT 'blur',
    subtitle_lang TEXT DEFAULT 'id',
    status       TEXT DEFAULT 'pending',
    error_msg    TEXT,
    file_path    TEXT,
    file_size    INTEGER,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    video_id    TEXT,
    clip_id     TEXT,
    job_type    TEXT NOT NULL,
    status      TEXT DEFAULT 'pending',
    phase       TEXT,
    progress    INTEGER DEFAULT 0,
    message     TEXT,
    error_msg   TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS rate_limits (
    ip          TEXT NOT NULL,
    window_start DATETIME NOT NULL,
    count       INTEGER DEFAULT 1,
    PRIMARY KEY (ip, window_start)
);
"""


async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.executescript(CREATE_SQL)
        await db.commit()


async def get_db():
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        yield db
