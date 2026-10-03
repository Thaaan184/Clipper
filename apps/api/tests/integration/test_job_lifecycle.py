import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from clipforge.api.app import app
from clipforge.core.config import settings
from clipforge.db.connection import get_db_connection
from clipforge.db.migrator import run_migrations
from clipforge.jobs.events import broadcaster
from clipforge.jobs.models import JobStatus
from clipforge.jobs.state_machine import recover_orphaned_jobs


@pytest.fixture(autouse=True)
async def setup_test_db(tmp_path: Path):
    test_db = tmp_path / "test.db"
    settings.db_path = test_db
    settings.data_dir = tmp_path
    async with get_db_connection(test_db) as db:
        await run_migrations(db)
    yield


@pytest.mark.asyncio
async def test_invalid_url_rejected():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Non-https
        res = await client.post(
            "/api/jobs", json={"source_url": "http://youtube.com/watch?v=12345678901"}
        )
        assert res.status_code == 400
        assert res.headers["content-type"] == "application/problem+json"
        assert res.json()["code"] == "INVALID_URL"

        # Disallowed host
        res2 = await client.post(
            "/api/jobs", json={"source_url": "https://malicious.com/watch?v=12345678901"}
        )
        assert res2.status_code == 403
        assert res2.json()["code"] == "HOST_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_job_lifecycle_to_review():
    with (
        patch("clipforge.api.routes.jobs.stage_validate", new_callable=AsyncMock) as m_val,
        patch("clipforge.api.routes.jobs.stage_fetch_signals", new_callable=AsyncMock) as m_fetch,
        patch("clipforge.api.routes.jobs.stage_analyze_signals", new_callable=AsyncMock) as m_ana,
        patch("clipforge.api.routes.jobs.stage_fuse_candidates", new_callable=AsyncMock) as m_fuse,
        patch("clipforge.api.routes.jobs.stage_targeted_asr", new_callable=AsyncMock) as m_asr,
        patch("clipforge.api.routes.jobs.stage_scout_rerank", new_callable=AsyncMock) as m_scout,
    ):
        m_val.return_value = (["meta.json"], {"valid": True})
        m_fetch.return_value = (["audio.m4a"], {"downloaded": True})
        m_ana.return_value = (["audio_features.json"], {"extracted": True})
        m_fuse.return_value = (["timeline.json"], {"candidates": 5})
        m_asr.return_value = (["transcripts.json"], {"transcribed": 5})
        m_scout.return_value = (["timeline.json"], {"approved": 5})

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            res = await client.post(
                "/api/jobs", json={"source_url": "https://www.youtube.com/watch?v=cLhVLsius9w"}
            )
            assert res.status_code == 202
            job_data = res.json()
            job_id = job_data["id"]
            assert job_data["status"] == "queued"

            # Wait for stages to progress
            for _ in range(50):
                await asyncio.sleep(0.05)
                status_res = await client.get(f"/api/jobs/{job_id}")
                current = status_res.json()["status"]
                if current in ["awaiting_review", "failed"]:
                    break

            final_res = await client.get(f"/api/jobs/{job_id}")
            assert final_res.status_code == 200
            assert final_res.json()["status"] == "awaiting_review"
            assert final_res.json()["progress"] == 1.0


@pytest.mark.asyncio
async def test_job_cancel():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        res = await client.post(
            "/api/jobs", json={"source_url": "https://www.youtube.com/watch?v=RRJ2XZOkUOU"}
        )
        job_id = res.json()["id"]

        cancel_res = await client.post(f"/api/jobs/{job_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"

        # Verify status in DB
        get_res = await client.get(f"/api/jobs/{job_id}")
        assert get_res.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_restart_recovery(tmp_path: Path):
    async with get_db_connection() as db:
        # Create an orphaned running job
        await db.execute(
            """
            INSERT INTO jobs (id, source_url, genre, language, params_json, status, progress, created_at, updated_at)
            VALUES ('orphan_1', 'https://youtube.com/watch?v=3DvqXuKxDHk', 'gaming', 'id', '{}', 'running', 0.5, '2026-10-04T00:00:00Z', '2026-10-04T00:00:00Z')
            """
        )
        await db.commit()

        recovered = await recover_orphaned_jobs(db)
        assert "orphan_1" in recovered

        async with db.execute("SELECT status FROM jobs WHERE id = 'orphan_1'") as cursor:
            row = await cursor.fetchone()
            assert row[0] == JobStatus.QUEUED.value


@pytest.mark.asyncio
async def test_sse_replay():
    async with get_db_connection() as db:
        # Create a job and events
        await db.execute(
            """
            INSERT INTO jobs (id, source_url, genre, language, params_json, status, progress, created_at, updated_at)
            VALUES ('job_sse_1', 'https://youtube.com/watch?v=cLhVLsius9w', 'gaming', 'id', '{}', 'running', 0.1, '2026-10-04T00:00:00Z', '2026-10-04T00:00:00Z')
            """
        )
        await db.commit()

        ev1 = await broadcaster.publish(db, "job_sse_1", "stage_completed", {"stage": "validate"})
        ev2 = await broadcaster.publish(
            db, "job_sse_1", "stage_completed", {"stage": "fetch_signals"}
        )
        assert ev1.id is not None
        assert ev2.id is not None

        # Replay events after ev1.id
        replayed = await broadcaster.replay_events_since(db, "job_sse_1", ev1.id)
        assert len(replayed) == 1
        assert replayed[0].payload == {"stage": "fetch_signals"}
