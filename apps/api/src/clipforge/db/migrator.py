"""SQL migration runner."""

from datetime import UTC, datetime
from pathlib import Path

import aiosqlite

from clipforge.core.logging import logger

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


async def run_migrations(db: aiosqlite.Connection) -> list[str]:
    """Execute all unapplied SQL migration files in sequence."""
    await db.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
    """)
    await db.commit()

    async with db.execute("SELECT version FROM schema_migrations") as cursor:
        rows = await cursor.fetchall()
        applied = {row[0] for row in rows}

    applied_now = []
    sql_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    for sql_file in sql_files:
        version = sql_file.name
        if version not in applied:
            logger.info("Applying database migration", version=version)
            sql_content = sql_file.read_text(encoding="utf-8")
            await db.executescript(sql_content)
            now_iso = datetime.now(UTC).isoformat()
            await db.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, now_iso),
            )
            await db.commit()
            applied_now.append(version)

    return applied_now
