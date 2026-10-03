"""Integration tests for Timeline API and Candidates API endpoints."""

import json
from pathlib import Path

import httpx
import pytest

from clipforge.api.app import app
from clipforge.core.config import settings
from clipforge.db.connection import get_db_connection


@pytest.mark.asyncio
async def test_timeline_and_candidates_endpoints(tmp_path: Path):
    job_id = "test_job_timeline_1"

    async with get_db_connection() as db:
        await db.execute(
            """
            INSERT INTO jobs (id, source_url, genre, language, params_json, status, progress, duration_s, title, created_at, updated_at)
            VALUES (?, 'https://www.youtube.com/watch?v=cLhVLsius9w', 'gaming', 'id', '{}', 'awaiting_review', 1.0, 120.0, 'Epic Apex Stream', '2026-10-04T00:00:00Z', '2026-10-04T00:00:00Z')
            """,
            (job_id,),
        )
        await db.execute(
            """
            INSERT INTO candidates (id, job_id, rank, start_s, end_s, peak_s, signal_score, final_score, category, title, hook_text, reason, evidence_json, flags_json, status)
            VALUES ('cand_1', ?, 1, 10.0, 45.0, 25.0, 0.88, 0.88, 'gameplay_highlight', 'Squad Wipe', 'Watch this wipe', 'Triple kill', '{"signals": {"loud_surge": 0.9}}', '[]', 'proposed')
            """,
            (job_id,),
        )
        await db.commit()

    # Also write a dummy timeline.json artifact
    job_dir = settings.data_dir / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    timeline_file = job_dir / "timeline.json"
    timeline_file.write_text(
        json.dumps(
            {
                "job_id": job_id,
                "duration_s": 120.0,
                "hop_s": 1.0,
                "signals": {
                    "fused_score": [0.1] * 120,
                    "loud_surge": [0.05] * 120,
                },
                "candidates": [
                    {
                        "id": "cand_1",
                        "rank": 1,
                        "start_s": 10.0,
                        "end_s": 45.0,
                        "peak_s": 25.0,
                        "duration_s": 35.0,
                        "signal_score": 0.88,
                        "final_score": 0.88,
                        "category": "gameplay_highlight",
                        "title": "Squad Wipe",
                        "hook_text": "Watch this wipe",
                        "reason": "Triple kill",
                        "evidence": {"signals": {"loud_surge": 0.9}},
                        "flags": [],
                        "status": "proposed",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. Test GET /api/jobs/{id}/timeline
        res_tl = await client.get(f"/api/jobs/{job_id}/timeline")
        assert res_tl.status_code == 200
        tl_data = res_tl.json()
        assert tl_data["job_id"] == job_id
        assert tl_data["duration_s"] == 120.0
        assert "fused_score" in tl_data["signals"]
        assert len(tl_data["candidates"]) == 1
        assert tl_data["candidates"][0]["title"] == "Squad Wipe"

        # 2. Test GET /api/jobs/{id}/candidates
        res_cand = await client.get(f"/api/jobs/{job_id}/candidates")
        assert res_cand.status_code == 200
        cand_data = res_cand.json()
        assert cand_data["job_id"] == job_id
        assert cand_data["total_candidates"] == 1
        assert cand_data["candidates"][0]["id"] == "cand_1"
        assert cand_data["candidates"][0]["start_s"] == 10.0
        assert cand_data["candidates"][0]["end_s"] == 45.0
