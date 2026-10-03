"""FastAPI application factory and lifespan configuration."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from clipforge.api.routes import health, jobs
from clipforge.core.config import settings
from clipforge.core.errors import ClipForgeError, problem_exception_handler
from clipforge.core.logging import logger, setup_logging
from clipforge.db.connection import get_db_connection
from clipforge.db.migrator import run_migrations
from clipforge.jobs.state_machine import recover_orphaned_jobs


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle management."""
    setup_logging()
    logger.info("Initializing ClipForge API v2...")

    # Run database migrations
    async with get_db_connection() as db:
        applied = await run_migrations(db)
        if applied:
            logger.info("Applied database migrations", migrations=applied)
        recovered = await recover_orphaned_jobs(db)
        if recovered:
            logger.info("Recovered orphaned jobs", count=len(recovered))

    yield

    logger.info("Shutting down ClipForge API v2.")


def create_app() -> FastAPI:
    """Create and configure FastAPI instance."""
    app = FastAPI(
        title="ClipForge API",
        version="2.0.0",
        description="Signal-first, LLM-last gaming video clipper API",
        lifespan=lifespan,
    )

    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handlers
    app.add_exception_handler(ClipForgeError, problem_exception_handler)  # type: ignore

    # Routers
    app.include_router(health.router)
    app.include_router(jobs.router)

    return app


app = create_app()
