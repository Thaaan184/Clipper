"""Job state transitions and recovery logic."""

from datetime import UTC, datetime

import aiosqlite

from clipforge.core.errors import ConflictError
from clipforge.core.logging import logger
from clipforge.jobs.events import broadcaster
from clipforge.jobs.models import JobStatus

VALID_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED},
    JobStatus.RUNNING: {
        JobStatus.RUNNING,
        JobStatus.AWAITING_REVIEW,
        JobStatus.RENDERING,
        JobStatus.DONE,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.AWAITING_REVIEW: {JobStatus.RENDERING, JobStatus.CANCELLED},
    JobStatus.RENDERING: {
        JobStatus.RENDERING,
        JobStatus.DONE,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.DONE: set(),
    JobStatus.FAILED: set(),
    JobStatus.CANCELLED: set(),
}


async def transition_job_status(
    db: aiosqlite.Connection,
    job_id: str,
    new_status: JobStatus,
    stage: str | None = None,
    progress: float | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    """Validate and persist an atomic state transition."""
    async with db.execute(
        "SELECT status FROM jobs WHERE id = ?",
        (job_id,),
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            raise ValueError(f"Job {job_id} not found")
        current_status = JobStatus(row[0])

    if new_status not in VALID_TRANSITIONS.get(current_status, set()):
        raise ConflictError(
            f"Invalid transition from {current_status.value} to {new_status.value} for job {job_id}"
        )

    now_iso = datetime.now(UTC).isoformat()
    finished_at = (
        now_iso if new_status in {JobStatus.DONE, JobStatus.FAILED, JobStatus.CANCELLED} else None
    )

    fields = ["status = ?", "updated_at = ?"]
    values: list[object] = [new_status.value, now_iso]

    if stage is not None:
        fields.append("stage = ?")
        values.append(stage)
    if progress is not None:
        fields.append("progress = ?")
        values.append(progress)
    if error_code is not None:
        fields.append("error_code = ?")
        values.append(error_code)
    if error_message is not None:
        fields.append("error_message = ?")
        values.append(error_message)
    if finished_at is not None:
        fields.append("finished_at = ?")
        values.append(finished_at)

    values.append(job_id)
    query = f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?"
    await db.execute(query, values)
    await db.commit()

    logger.info(
        "Job status updated",
        job_id=job_id,
        from_status=current_status.value,
        to_status=new_status.value,
        stage=stage,
    )

    await broadcaster.publish(
        db=db,
        job_id=job_id,
        event_type="status_change",
        payload={
            "job_id": job_id,
            "status": new_status.value,
            "stage": stage,
            "progress": progress,
            "error_code": error_code,
            "error_message": error_message,
        },
    )


async def recover_orphaned_jobs(db: aiosqlite.Connection) -> list[str]:
    """Find jobs left in RUNNING or RENDERING status upon server restart and reset to QUEUED for resumption."""
    now_iso = datetime.now(UTC).isoformat()
    async with db.execute("SELECT id FROM jobs WHERE status IN ('running', 'rendering')") as cursor:
        rows = await cursor.fetchall()
        orphan_ids = [row[0] for row in rows]

    if orphan_ids:
        logger.warn("Recovering orphaned jobs from previous server run", job_ids=orphan_ids)
        await db.execute(
            """
            UPDATE jobs
            SET status = 'queued', updated_at = ?
            WHERE status IN ('running', 'rendering')
            """,
            (now_iso,),
        )
        await db.commit()

    return orphan_ids
