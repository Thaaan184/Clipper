from pathlib import Path

import pytest

from clipforge.db.connection import get_db_connection
from clipforge.db.migrator import run_migrations


@pytest.mark.asyncio
async def test_migrations_applied_cleanly(tmp_path: Path):
    db_file = tmp_path / "test_migration.db"
    async with get_db_connection(db_file) as db:
        applied = await run_migrations(db)
        assert len(applied) >= 1
        assert "0001_initial.sql" in applied

        # Running again is idempotent (applies 0 new migrations)
        second_run = await run_migrations(db)
        assert len(second_run) == 0

        # Verify tables created
        async with db.execute("SELECT name FROM sqlite_master WHERE type='table'") as cursor:
            tables = {row[0] for row in await cursor.fetchall()}
            assert "jobs" in tables
            assert "stage_runs" in tables
            assert "events" in tables
            assert "candidates" in tables
            assert "clips" in tables
            assert "subtitle_tracks" in tables
            assert "subtitle_words" in tables
            assert "feedback" in tables
            assert "glossary" in tables
