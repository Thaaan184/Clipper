"""End-to-end integration test of Phase 4 Candidate Quality pipeline."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
import scipy.io.wavfile as wavfile

from clipforge.api.app import app
from clipforge.core.config import settings
from clipforge.db.connection import get_db_connection
from clipforge.db.migrator import run_migrations
from clipforge.ingest.models import VideoMetadata
from clipforge.jobs.pipeline import (
    stage_analyze_signals,
    stage_fetch_signals,
    stage_fuse_candidates,
    stage_scout_rerank,
    stage_targeted_asr,
    stage_validate,
)
from clipforge.timeline.service import get_candidates_for_job


@pytest.fixture(autouse=True)
async def setup_test_env(tmp_path: Path):
    test_db = tmp_path / "test.db"
    settings.db_path = test_db
    settings.data_dir = tmp_path
    async with get_db_connection(test_db) as db:
        await run_migrations(db)
    yield


@pytest.mark.asyncio
async def test_pipeline_fase4_full_quality_cycle(tmp_path: Path):
    job_id = "test-job-fase4"
    job_dir = tmp_path / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    async with get_db_connection() as db:
        # 1. Insert initial job
        now = "2026-10-04T00:00:00Z"
        await db.execute(
            """
            INSERT INTO jobs (id, source_url, genre, language, params_json, status, progress, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 0.0, ?, ?)
            """,
            (
                job_id,
                "https://www.youtube.com/watch?v=cLhVLsius9w",
                "gaming",
                "id",
                "{}",
                "running",
                now,
                now,
            ),
        )
        await db.commit()

        # 2. Stage 1: Validate
        mock_meta = VideoMetadata(
            video_id="cLhVLsius9w",
            canonical_url="https://www.youtube.com/watch?v=cLhVLsius9w",
            title="Apex Legends Stream",
            duration_s=120.0,
            has_chat=True,
            has_heatmap=False,
        )
        with patch("clipforge.jobs.pipeline.probe_video", new_callable=AsyncMock) as m_probe:
            m_probe.return_value = mock_meta
            await stage_validate(db, job_id, {"source_url": mock_meta.canonical_url})

        # 3. Create synthetic audio file (120 seconds, 16kHz mono)
        sample_rate = 16000
        total_samples = 120 * sample_rate
        audio_data = np.zeros(total_samples, dtype=np.int16)

        # Inject high-amplitude burst at 40s - 75s (combat)
        t = np.linspace(0, 35, 35 * sample_rate, endpoint=False)
        tone = (0.7 * 32767 * np.sin(2 * np.pi * 440 * t)).astype(np.int16)
        audio_data[40 * sample_rate : 75 * sample_rate] = tone

        audio_path = job_dir / "audio_raw.wav"
        wavfile.write(str(audio_path), sample_rate, audio_data)

        # Create synthetic chat JSON
        chat_path = job_dir / "chat.json"
        chat_events = [
            {"offset_s": 50.0, "message": "rata semua squad wipe wkwk gg"},
            {"offset_s": 52.0, "message": "gila jago banget clutch"},
            {"offset_s": 55.0, "message": "clip bang clip ini"},
        ]
        chat_lines = [
            json.dumps({"replayChatItemAction": {"actions": [{"addChatItemAction": {"item": {"liveChatTextMessageRenderer": {"message": {"runs": [{"text": e["message"]}]}, "videoOffsetTimeMsec": str(int(e["offset_s"] * 1000))}}}}]}})
            for e in chat_events
        ]
        chat_path.write_text("\n".join(chat_lines), encoding="utf-8")

        # 4. Stage 3: Analyze Signals
        await stage_analyze_signals(db, job_id, {})

        # 5. Stage 4: Fuse Candidates
        await stage_fuse_candidates(db, job_id, {"genre": "gaming"})

        cands_after_fuse = await get_candidates_for_job(job_id, db)
        assert len(cands_after_fuse.candidates) > 0

        # 6. Stage 5: Targeted ASR
        # Mock Whisper model inside transcribe_candidate_slice
        from unittest.mock import MagicMock
        mock_seg = MagicMock()
        mock_seg.text = "squad rata semua"
        mock_w1 = MagicMock()
        mock_w1.word = "squad"
        mock_w1.start = 1.0
        mock_w1.end = 1.5
        mock_w1.probability = 0.9
        mock_w2 = MagicMock()
        mock_w2.word = "rata!"
        mock_w2.start = 1.6
        mock_w2.end = 2.2
        mock_w2.probability = 0.9
        mock_seg.words = [mock_w1, mock_w2]

        mock_info = MagicMock()
        mock_info.language = "id"

        mock_whisper = MagicMock()
        mock_whisper.transcribe.return_value = ([mock_seg], mock_info)

        with patch("clipforge.asr.whisper.get_whisper_model", return_value=mock_whisper):
            await stage_targeted_asr(db, job_id, {"genre": "gaming"})

        # Check transcript artifacts created
        transcripts = list((job_dir / "transcripts").glob("*.json"))
        assert len(transcripts) > 0

        # 7. Stage 6: Scout and Re-rank (with heuristic fallback)
        await stage_scout_rerank(db, job_id, {"genre": "gaming"})

        # 8. Verify results
        final_cands = await get_candidates_for_job(job_id, db)
        assert len(final_cands.candidates) > 0

        top_cand = final_cands.candidates[0]
        assert top_cand.rank == 1
        assert top_cand.status in ("proposed", "approved")
        assert top_cand.title != ""
        assert top_cand.hook_text != ""
        assert top_cand.category in ("gameplay_highlight", "funny_fail", "clutch")

        # Verify timeline.json updated
        timeline_file = job_dir / "timeline.json"
        assert timeline_file.exists()
        tl_data = json.loads(timeline_file.read_text(encoding="utf-8"))
        assert tl_data["candidates"][0]["title"] == top_cand.title
