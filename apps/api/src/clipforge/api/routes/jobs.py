"""Job management API endpoints."""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from urllib.parse import urlparse

import aiosqlite
from fastapi import APIRouter, Depends, Header, status
from fastapi.responses import StreamingResponse

from clipforge.core.config import settings
from clipforge.core.errors import HostNotAllowedError, InvalidUrlError, JobNotFoundError
from clipforge.core.logging import logger
from clipforge.db.connection import get_db
from clipforge.jobs.engine import engine
from clipforge.jobs.events import broadcaster
from clipforge.jobs.models import JobCreateRequest, JobEvent, JobResponse, JobStatus, StageName
from clipforge.jobs.state_machine import transition_job_status

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


def _validate_source_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise InvalidUrlError("Scheme must be https")
    if not parsed.hostname or parsed.hostname.lower() not in settings.allowed_hosts:
        raise HostNotAllowedError(f"Host '{parsed.hostname}' not in allowed hosts")


async def _execute_job_pipeline(job_id: str) -> None:
    """Mock pipeline runner for Phase 2 scaffold validation."""
    from clipforge.db.connection import get_db_connection

    async with get_db_connection() as db:
        try:
            # Mock Stage 1: Validate
            async def _stage_validate(
                d: aiosqlite.Connection, j_id: str, inp: dict[str, object]
            ) -> tuple[list[str], dict[str, object]]:
                await asyncio.sleep(0.05)
                return (["meta.json"], {"valid": True})

            # Mock Stage 2: Fetch Signals
            async def _stage_fetch_signals(
                d: aiosqlite.Connection, j_id: str, inp: dict[str, object]
            ) -> tuple[list[str], dict[str, object]]:
                await asyncio.sleep(0.05)
                return (["signals/audio.npz"], {"audio_extracted": True})

            # Mock Stage 3: Analyze Signals
            async def _stage_analyze_signals(
                d: aiosqlite.Connection, j_id: str, inp: dict[str, object]
            ) -> tuple[list[str], dict[str, object]]:
                await asyncio.sleep(0.05)
                return (["signals/fused.npz"], {"peaks_found": 5})

            stages: list[tuple[StageName, object, float]] = [
                (StageName.VALIDATE, _stage_validate, 0.2),
                (StageName.FETCH_SIGNALS, _stage_fetch_signals, 0.5),
                (StageName.ANALYZE_SIGNALS, _stage_analyze_signals, 0.8),
            ]

            for stage_name, stage_fn, prog in stages:
                if engine.is_cancelled(job_id):
                    break
                await engine.run_stage(
                    db=db,
                    job_id=job_id,
                    stage=stage_name,
                    stage_fn=stage_fn,  # type: ignore
                    stage_input={"job_id": job_id, "mock": True},
                    progress=prog,
                )

            if engine.is_cancelled(job_id):
                await transition_job_status(db, job_id, JobStatus.CANCELLED)
            else:
                await transition_job_status(db, job_id, JobStatus.AWAITING_REVIEW, progress=1.0)

        except asyncio.CancelledError:
            await transition_job_status(db, job_id, JobStatus.CANCELLED)
        except Exception as e:
            logger.error("Job pipeline execution failed", job_id=job_id, error=str(e))
            await transition_job_status(
                db,
                job_id,
                JobStatus.FAILED,
                error_code="PIPELINE_ERROR",
                error_message=str(e),
            )


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=JobResponse)
async def create_job(
    req: JobCreateRequest,
    db: aiosqlite.Connection = Depends(get_db),
) -> JobResponse:
    """Create a new clipping job and schedule pipeline execution."""
    _validate_source_url(req.source_url)

    job_id = str(uuid.uuid4())
    now_iso = datetime.now(UTC).isoformat()
    params_json = req.model_dump_json()

    await db.execute(
        """
        INSERT INTO jobs (id, source_url, genre, language, params_json, status, progress, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 0.0, ?, ?)
        """,
        (
            job_id,
            req.source_url,
            req.genre,
            req.language,
            params_json,
            JobStatus.QUEUED.value,
            now_iso,
            now_iso,
        ),
    )
    await db.commit()

    # Schedule background execution
    task = asyncio.create_task(_execute_job_pipeline(job_id))
    engine._active_tasks[job_id] = task

    return JobResponse(
        id=job_id,
        source_url=req.source_url,
        genre=req.genre,
        language=req.language,
        status=JobStatus.QUEUED,
        progress=0.0,
        created_at=now_iso,
        updated_at=now_iso,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_status(
    job_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> JobResponse:
    """Retrieve full details of a specific job."""
    async with db.execute(
        """
        SELECT id, source_url, video_id, title, duration_s, genre, language,
               status, stage, progress, error_code, error_message,
               created_at, updated_at, finished_at
        FROM jobs WHERE id = ?
        """,
        (job_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise JobNotFoundError(f"Job {job_id} not found")

        return JobResponse(
            id=row[0],
            source_url=row[1],
            video_id=row[2],
            title=row[3],
            duration_s=row[4],
            genre=row[5],
            language=row[6],
            status=JobStatus(row[7]),
            stage=row[8],
            progress=row[9],
            error_code=row[10],
            error_message=row[11],
            created_at=row[12],
            updated_at=row[13],
            finished_at=row[14],
        )


@router.post("/{job_id}/cancel", status_code=status.HTTP_200_OK)
async def cancel_job(
    job_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict[str, str]:
    """Idempotently cancel a job."""
    async with db.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise JobNotFoundError(f"Job {job_id} not found")
        current_status = JobStatus(row[0])

    if current_status in {JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED}:
        return {"status": current_status.value, "message": "Job already terminated"}

    engine.request_cancel(job_id)
    await transition_job_status(db, job_id, JobStatus.CANCELLED)
    return {"status": JobStatus.CANCELLED.value, "message": "Job cancelled successfully"}


@router.get("/{job_id}/events")
async def stream_job_events(
    job_id: str,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    db: aiosqlite.Connection = Depends(get_db),
) -> StreamingResponse:
    """Stream SSE events for a job with Last-Event-ID replay and 15s heartbeats."""
    async with db.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise JobNotFoundError(f"Job {job_id} not found")

    queue = await broadcaster.subscribe(job_id)

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Replay historical events if Last-Event-ID provided
            if last_event_id and last_event_id.isdigit():
                replay_list = await broadcaster.replay_events_since(db, job_id, int(last_event_id))
                for ev in replay_list:
                    yield f"id: {ev.id}\nevent: {ev.type}\ndata: {json.dumps(ev.payload)}\n\n"

            while True:
                try:
                    ev_live: JobEvent = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"id: {ev_live.id}\nevent: {ev_live.type}\ndata: {json.dumps(ev_live.payload)}\n\n"
                except TimeoutError:
                    # Heartbeat comment to keep connection alive
                    yield ": ping\n\n"
        finally:
            await broadcaster.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
