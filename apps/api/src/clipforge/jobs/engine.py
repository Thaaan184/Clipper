"""Pipeline stage execution engine with cancellation and checkpointing."""

import asyncio
import time
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from clipforge.core.logging import logger
from clipforge.jobs.checkpoints import CheckpointManager, compute_hash
from clipforge.jobs.events import broadcaster
from clipforge.jobs.models import JobStatus, StageName, StageStatus
from clipforge.jobs.state_machine import transition_job_status


class JobEngine:
    """Orchestrates pipeline stage execution with cancellation and idempotency."""

    def __init__(self) -> None:
        self._cancellation_tokens: dict[str, asyncio.Event] = {}
        self._active_tasks: dict[str, asyncio.Task[None]] = {}

    def get_cancel_token(self, job_id: str) -> asyncio.Event:
        if job_id not in self._cancellation_tokens:
            self._cancellation_tokens[job_id] = asyncio.Event()
        return self._cancellation_tokens[job_id]

    def is_cancelled(self, job_id: str) -> bool:
        token = self._cancellation_tokens.get(job_id)
        return token.is_set() if token else False

    def request_cancel(self, job_id: str) -> bool:
        """Signal cancellation to a running job."""
        if job_id in self._cancellation_tokens:
            self._cancellation_tokens[job_id].set()
            task = self._active_tasks.get(job_id)
            if task and not task.done():
                task.cancel()
            return True
        return False

    async def run_stage(
        self,
        db: aiosqlite.Connection,
        job_id: str,
        stage: StageName,
        stage_fn: Callable[
            [aiosqlite.Connection, str, dict[str, Any]],
            Coroutine[Any, Any, tuple[list[str], dict[str, Any]]],
        ],
        stage_input: dict[str, Any],
        progress: float,
        force: bool = False,
    ) -> bool:
        """Run a single stage with checkpoint skip check, stage_runs logging, and cancellation check."""
        if self.is_cancelled(job_id):
            logger.info("Stage skipped due to job cancellation", job_id=job_id, stage=stage.value)
            return False

        ckpt = CheckpointManager(job_id)
        input_hash = compute_hash(stage_input)

        # Idempotent skip if checkpoint already satisfied
        if not force and ckpt.is_stage_completed(stage.value, input_hash):
            logger.info("Stage checkpoint valid, skipping", job_id=job_id, stage=stage.value)
            await self._record_stage_run(
                db=db,
                job_id=job_id,
                stage=stage.value,
                status=StageStatus.SKIPPED,
                input_hash=input_hash,
                duration_ms=0,
                metrics={"skipped": True},
            )
            return True

        # Transition job state
        target_status = (
            JobStatus.RENDERING if stage == StageName.RENDER_CLIPS else JobStatus.RUNNING
        )
        await transition_job_status(
            db=db,
            job_id=job_id,
            new_status=target_status,
            stage=stage.value,
            progress=progress,
        )

        start_time = time.monotonic()
        now_iso = datetime.now(UTC).isoformat()

        # Record stage running
        cursor = await db.execute(
            """
            INSERT INTO stage_runs (job_id, stage, attempt, status, input_hash, started_at)
            VALUES (?, ?, 1, ?, ?, ?)
            """,
            (job_id, stage.value, StageStatus.RUNNING.value, input_hash, now_iso),
        )
        await db.commit()
        run_id = cursor.lastrowid

        try:
            # Execute actual stage coroutine
            outputs, metrics = await stage_fn(db, job_id, stage_input)

            if self.is_cancelled(job_id):
                raise asyncio.CancelledError(f"Job {job_id} cancelled during {stage.value}")

            duration_ms = int((time.monotonic() - start_time) * 1000)
            ckpt.save_checkpoint(stage.value, input_hash, outputs, metrics)

            await db.execute(
                """
                UPDATE stage_runs
                SET status = ?, finished_at = ?, duration_ms = ?, metrics_json = ?
                WHERE id = ?
                """,
                (
                    StageStatus.SUCCEEDED.value,
                    datetime.now(UTC).isoformat(),
                    duration_ms,
                    str(metrics),
                    run_id,
                ),
            )
            await db.commit()

            await broadcaster.publish(
                db=db,
                job_id=job_id,
                event_type="stage_completed",
                payload={"stage": stage.value, "duration_ms": duration_ms, "metrics": metrics},
            )
            return True

        except asyncio.CancelledError:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            await db.execute(
                """
                UPDATE stage_runs
                SET status = ?, finished_at = ?, duration_ms = ?, error = 'Cancelled'
                WHERE id = ?
                """,
                (StageStatus.FAILED.value, datetime.now(UTC).isoformat(), duration_ms, run_id),
            )
            await db.commit()
            raise

        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            err_msg = str(e)
            logger.error("Stage execution failed", job_id=job_id, stage=stage.value, error=err_msg)
            await db.execute(
                """
                UPDATE stage_runs
                SET status = ?, finished_at = ?, duration_ms = ?, error = ?
                WHERE id = ?
                """,
                (
                    StageStatus.FAILED.value,
                    datetime.now(UTC).isoformat(),
                    duration_ms,
                    err_msg,
                    run_id,
                ),
            )
            await db.commit()
            raise

    async def _record_stage_run(
        self,
        db: aiosqlite.Connection,
        job_id: str,
        stage: str,
        status: StageStatus,
        input_hash: str,
        duration_ms: int,
        metrics: dict[str, Any],
    ) -> None:
        now_iso = datetime.now(UTC).isoformat()
        await db.execute(
            """
            INSERT INTO stage_runs (job_id, stage, attempt, status, input_hash, started_at, finished_at, duration_ms, metrics_json)
            VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, stage, status.value, input_hash, now_iso, now_iso, duration_ms, str(metrics)),
        )
        await db.commit()


engine = JobEngine()
