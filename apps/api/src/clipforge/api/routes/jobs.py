"""Job management API endpoints."""

import asyncio
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import aiosqlite
from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from clipforge.core.config import settings
from clipforge.core.errors import HostNotAllowedError, InvalidUrlError, JobNotFoundError
from clipforge.core.logging import logger
from clipforge.db.connection import get_db
from clipforge.jobs.engine import engine
from clipforge.jobs.events import broadcaster
from clipforge.jobs.models import JobCreateRequest, JobEvent, JobResponse, JobStatus, StageName
from clipforge.jobs.pipeline import (
    stage_analyze_signals,
    stage_fetch_signals,
    stage_fuse_candidates,
    stage_render_clips,
    stage_scout_rerank,
    stage_targeted_asr,
    stage_validate,
)
from clipforge.jobs.state_machine import transition_job_status
from clipforge.timeline.models import CandidatesResponse, TimelineResponse
from clipforge.timeline.service import get_candidates_for_job, get_timeline_for_job

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


def _validate_source_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise InvalidUrlError("Scheme must be https")
    if not parsed.hostname or parsed.hostname.lower() not in settings.allowed_hosts:
        raise HostNotAllowedError(f"Host '{parsed.hostname}' not in allowed hosts")


async def _execute_job_pipeline(job_id: str) -> None:
    """Execute pipeline stages: Validate -> Fetch Signals -> Analyze Signals -> Fuse Candidates."""
    from clipforge.db.connection import get_db_connection

    async with get_db_connection() as db:
        try:
            # Query initial job params
            async with db.execute(
                "SELECT source_url, genre, language FROM jobs WHERE id = ?", (job_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return
                source_url, genre, language = row[0], row[1], row[2]

            stage_input = {
                "job_id": job_id,
                "source_url": source_url,
                "genre": genre,
                "language": language,
            }

            stages: list[tuple[StageName, Any, float]] = [
                (StageName.VALIDATE, stage_validate, 0.15),
                (StageName.FETCH_SIGNALS, stage_fetch_signals, 0.35),
                (StageName.ANALYZE_SIGNALS, stage_analyze_signals, 0.55),
                (StageName.FUSE_CANDIDATES, stage_fuse_candidates, 0.70),
                (StageName.TARGETED_ASR, stage_targeted_asr, 0.85),
                (StageName.SCOUT_RERANK, stage_scout_rerank, 0.95),
            ]

            for stage_name, stage_fn, prog in stages:
                if engine.is_cancelled(job_id):
                    break
                success = await engine.run_stage(
                    db=db,
                    job_id=job_id,
                    stage=stage_name,
                    stage_fn=stage_fn,
                    stage_input=stage_input,
                    progress=prog,
                )
                if not success and not engine.is_cancelled(job_id):
                    raise RuntimeError(f"Stage {stage_name.value} execution failed")

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


@router.delete("/{job_id}", status_code=status.HTTP_200_OK)
async def delete_job(
    job_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict[str, str]:
    """Delete a job, its database records, and its files on disk."""
    async with db.execute("SELECT id FROM jobs WHERE id = ?", (job_id,)) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise JobNotFoundError(f"Job {job_id} not found")

    # Cancel active tasks if running
    engine.request_cancel(job_id)
    active_task = engine._active_tasks.pop(f"render_{job_id}", None)
    if active_task and not active_task.done():
        active_task.cancel()

    # Clean up disk files
    try:
        import shutil

        from clipforge.jobs.pipeline import get_job_dir

        job_dir = get_job_dir(job_id)
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
    except Exception as exc:
        logger.warning("failed_to_delete_job_files", job_id=job_id, error=str(exc))

    # Clean up DB records in child tables
    await db.execute(
        "DELETE FROM subtitle_words WHERE track_id IN (SELECT id FROM subtitle_tracks WHERE clip_id IN (SELECT id FROM clips WHERE job_id = ?))",
        (job_id,),
    )
    await db.execute(
        "DELETE FROM subtitle_tracks WHERE clip_id IN (SELECT id FROM clips WHERE job_id = ?)",
        (job_id,),
    )
    await db.execute("DELETE FROM clips WHERE job_id = ?", (job_id,))
    await db.execute("DELETE FROM candidates WHERE job_id = ?", (job_id,))
    await db.execute("DELETE FROM timeline_signals WHERE job_id = ?", (job_id,))
    await db.execute("DELETE FROM job_events WHERE job_id = ?", (job_id,))
    await db.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    await db.commit()

    return {"status": "deleted", "job_id": job_id}



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


@router.get("/{job_id}/timeline", response_model=TimelineResponse)
async def get_job_timeline(
    job_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> TimelineResponse:
    """Retrieve multi-modal signal curves and candidate windows for a job."""
    return await get_timeline_for_job(job_id=job_id, db=db, data_dir=settings.data_dir)


@router.get("/{job_id}/candidates", response_model=CandidatesResponse)
async def get_job_candidates(
    job_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> CandidatesResponse:
    """Retrieve proposed candidate windows and signal evidence for review."""
    return await get_candidates_for_job(job_id=job_id, db=db)


class CandidateUpdatePayload(BaseModel):
    status: str | None = None  # kept | rejected | proposed
    user_start_s: float | None = None
    user_end_s: float | None = None


@router.patch("/candidates/{candidate_id}")
async def update_candidate_review(
    candidate_id: str,
    payload: CandidateUpdatePayload,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Update review status or manual timing boundaries for a candidate."""
    async with db.execute(
        "SELECT id, start_s, end_s FROM candidates WHERE id = ?", (candidate_id,)
    ) as cur:
        row = await cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")

    updates = []
    params: list[Any] = []

    if payload.status is not None:
        updates.append("status = ?")
        params.append(payload.status)

    if payload.user_start_s is not None:
        updates.append("user_start_s = ?")
        params.append(payload.user_start_s)

    if payload.user_end_s is not None:
        updates.append("user_end_s = ?")
        params.append(payload.user_end_s)

    if updates:
        params.append(candidate_id)
        await db.execute(f"UPDATE candidates SET {', '.join(updates)} WHERE id = ?", tuple(params))
        await db.commit()

    return {"status": "updated", "candidate_id": candidate_id}


@router.post("/{job_id}/render", status_code=status.HTTP_202_ACCEPTED)
async def trigger_job_render(
    job_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Trigger rendering for approved/kept candidate clips in this job."""
    async with db.execute(
        "SELECT id, source_url, genre, language, params_json FROM jobs WHERE id = ?", (job_id,)
    ) as cur:
        row = await cur.fetchone()
        if not row:
            raise JobNotFoundError(f"Job {job_id} not found")
        source_url, genre, language, params_json = row[1], row[2], row[3], row[4]

    params = json.loads(params_json) if params_json else {}
    stage_input = {
        "job_id": job_id,
        "source_url": source_url,
        "genre": genre,
        "language": language,
        "clip_count": params.get("clip_count", 5),
        "reframe_mode": params.get("reframe_mode", "blur"),
        "subtitle_style": params.get("subtitle_style", "classic_white"),
    }

    await transition_job_status(db, job_id, JobStatus.RENDERING, progress=0.80)

    async def _run_render_task() -> None:
        from clipforge.db.connection import get_db_connection

        async with get_db_connection() as task_db:
            try:
                success = await engine.run_stage(
                    db=task_db,
                    job_id=job_id,
                    stage=StageName.RENDER_CLIPS,
                    stage_fn=stage_render_clips,
                    stage_input=stage_input,
                    progress=1.0,
                )
                if success:
                    await transition_job_status(task_db, job_id, JobStatus.DONE, progress=1.0)
                else:
                    await transition_job_status(
                        task_db, job_id, JobStatus.FAILED, error_code="RENDER_FAILED"
                    )
            except Exception as exc:
                logger.error("Render execution failed", job_id=job_id, error=str(exc))
                await transition_job_status(
                    task_db,
                    job_id,
                    JobStatus.FAILED,
                    error_code="RENDER_FAILED",
                    error_message=str(exc),
                )

    task = asyncio.create_task(_run_render_task())
    engine._active_tasks[f"render_{job_id}"] = task
    return {"status": "rendering", "job_id": job_id}


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    limit: int = 10,
    db: aiosqlite.Connection = Depends(get_db),
) -> list[JobResponse]:
    """List recent jobs."""
    query = """
        SELECT id, source_url, video_id, title, duration_s, genre, language,
               status, stage, progress, error_code, error_message,
               created_at, updated_at, finished_at
        FROM jobs
        ORDER BY created_at DESC
        LIMIT ?
    """
    results: list[JobResponse] = []
    async with db.execute(query, (limit,)) as cursor:
        async for row in cursor:
            results.append(
                JobResponse(
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
            )
    return results


@router.get("/{job_id}/clips")
async def get_job_clips(
    job_id: str,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict[str, Any]:
    """Get all rendered clips for a given job."""
    query = """
        SELECT id, candidate_id, video_path, srt_path, duration_s, width, height,
               status, qa_json, created_at
        FROM clips
        WHERE job_id = ?
        ORDER BY created_at ASC
    """
    clips: list[dict[str, Any]] = []
    async with db.execute(query, (job_id,)) as cur:
        async for r in cur:
            qa_rep = json.loads(r[8]) if r[8] else None
            clips.append({
                "id": r[0],
                "job_id": job_id,
                "candidate_id": r[1],
                "file_path": r[2],
                "srt_path": r[3],
                "duration_s": r[4],
                "width": r[5],
                "height": r[6],
                "status": r[7],
                "qa": qa_rep,
                "created_at": r[9],
            })
    return {"clips": clips, "total": len(clips)}


