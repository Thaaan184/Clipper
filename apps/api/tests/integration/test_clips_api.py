"""Integration tests for Clips API and Subtitle Editor endpoints."""

from pathlib import Path

import httpx
import pytest

from clipforge.api.app import app
from clipforge.core.config import settings
from clipforge.db.connection import get_db_connection
from clipforge.db.migrator import run_migrations


@pytest.fixture(autouse=True)
async def setup_test_db(tmp_path: Path):
    test_db = tmp_path / "test.db"
    settings.db_path = test_db
    settings.data_dir = tmp_path
    async with get_db_connection(test_db) as db:
        await run_migrations(db)
    yield


@pytest.mark.asyncio
async def test_clips_crud_and_subtitles(tmp_path: Path):
    job_id = "job-101"
    clip_id = "clip-202"
    cand_id = "cand-303"

    clip_dir = tmp_path / "jobs" / job_id / "clips" / clip_id
    clip_dir.mkdir(parents=True, exist_ok=True)

    dummy_video = clip_dir / "final.mp4"
    dummy_video.write_bytes(b"dummy video data")

    dummy_srt = clip_dir / "clip.srt"
    dummy_srt.write_text("1\n00:00:01,000 --> 00:00:03,000\nSquad wipe!\n\n", encoding="utf-8")

    async with get_db_connection() as db:
        # Create job
        await db.execute(
            """
            INSERT INTO jobs (id, source_url, genre, language, params_json, status, progress, created_at, updated_at)
            VALUES (?, 'https://youtube.com/watch?v=cLhVLsius9w', 'gaming', 'id', '{}', 'done', 1.0, '2026-10-04T00:00:00Z', '2026-10-04T00:00:00Z')
            """,
            (job_id,),
        )
        # Create candidate
        await db.execute(
            """
            INSERT INTO candidates (id, job_id, rank, start_s, end_s, peak_s, signal_score, final_score, category, title, hook_text, reason, evidence_json, flags_json, status)
            VALUES (?, ?, 1, 10.0, 30.0, 20.0, 0.9, 0.9, 'gameplay_highlight', 'Squad Wipe', 'Rata!', 'Combat', '{}', '[]', 'rendered')
            """,
            (cand_id, job_id),
        )
        # Create clip
        await db.execute(
            """
            INSERT INTO clips (id, candidate_id, job_id, status, video_path, thumb_path, srt_path, width, height, duration_s, render_params_json, qa_json, created_at)
            VALUES (?, ?, ?, 'done', ?, NULL, ?, 1080, 1920, 20.0, '{"reframe_mode": "blur"}', '{"passed": true}', '2026-10-04T00:00:00Z')
            """,
            (clip_id, cand_id, job_id, str(dummy_video), str(dummy_srt)),
        )
        # Create subtitle track
        track_id = "track-1"
        await db.execute(
            """
            INSERT INTO subtitle_tracks (id, clip_id, revision, source, language, style_json, created_at)
            VALUES (?, ?, 1, 'asr', 'id', '{"preset": "classic_white"}', '2026-10-04T00:00:00Z')
            """,
            (track_id, clip_id),
        )
        await db.execute(
            """
            INSERT INTO subtitle_words (track_id, idx, start_s, end_s, text, confidence)
            VALUES (?, 0, 1.0, 2.5, 'Squad', 0.95), (?, 1, 2.5, 3.0, 'wipe!', 0.95)
            """,
            (track_id, track_id),
        )
        await db.commit()

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1. GET /api/clips/{id}
        res_clip = await client.get(f"/api/clips/{clip_id}")
        assert res_clip.status_code == 200
        assert res_clip.json()["id"] == clip_id
        assert res_clip.json()["width"] == 1080
        assert res_clip.json()["height"] == 1920

        # 2. GET /api/clips/{id}/subtitles
        res_subs = await client.get(f"/api/clips/{clip_id}/subtitles")
        assert res_subs.status_code == 200
        words = res_subs.json()["words"]
        assert len(words) == 2
        assert words[0]["text"] == "Squad"

        # 3. PUT /api/clips/{id}/subtitles (edit text)
        new_words = [
            {"idx": 0, "start_s": 1.0, "end_s": 2.5, "text": "Rata", "confidence": 1.0},
            {"idx": 1, "start_s": 2.5, "end_s": 3.0, "text": "semua!", "confidence": 1.0},
        ]
        res_put = await client.put(
            f"/api/clips/{clip_id}/subtitles",
            json={"words": new_words, "style_preset": "hormozi_bold"},
        )
        assert res_put.status_code == 200
        assert res_put.json()["revision"] == 2

        # 4. GET /api/clips/{id}/subtitles.srt
        res_srt = await client.get(f"/api/clips/{clip_id}/subtitles.srt")
        assert res_srt.status_code == 200
        assert "Squad wipe!" in res_srt.text or "Rata" in res_srt.text
