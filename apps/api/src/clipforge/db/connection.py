"""Database connection and lifecycle utilities."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from clipforge.core.config import settings


@asynccontextmanager
async def get_db_connection(
    db_path: Path | None = None,
) -> AsyncGenerator[aiosqlite.Connection, None]:
    """Provide an aiosqlite database connection configured with WAL and foreign keys."""
    target_path = db_path or settings.db_path
    target_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(target_path) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        await db.execute("PRAGMA busy_timeout=5000;")
        db.row_factory = aiosqlite.Row
        yield db


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Dependency provider for FastAPI route endpoints."""
    async with get_db_connection() as db:
        yield db
