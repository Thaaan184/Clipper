"""End-to-end integration test of the signals pipeline using synthetic audio."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
import scipy.io.wavfile

from clipforge.core.config import settings
from clipforge.db.connection import get_db_connection
from clipforge.ingest.models import IngestResult, VideoMetadata
from clipforge.jobs.engine import engine
from clipforge.jobs.models import JobStatus, StageName
from clipforge.jobs.pipeline import (
    stage_analyze_signals,
    stage_fetch_signals,
    stage_fuse_candidates,
    stage_validate,
)
from clipforge.jobs.state_machine import transition_job_status
from clipforge.timeline.service import get_timeline_for_job


@pytest.mark.asyncio
async def test_pipeline_signals_e2e(tmp_path: Path):
    job_id = "job_synthetic_e2e_1"
    job_dir = settings.data_dir / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate 60 seconds of synthetic audio with a huge action spike at seconds 30-38
    sr = 16000
    duration_s = 60.0
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    # Background hiss
    audio_data = np.random.uniform(-0.02, 0.02, len(t)).astype(np.float32)

    # Add 8 seconds of intense combat action (loud gunfire/spikes) at t=30 to t=38
    spike_idx_start = int(30 * sr)
    spike_idx_end = int(38 * sr)
    spike_t = t[spike_idx_start:spike_idx_end]
    combat_burst = 0.85 * np.sin(2 * np.pi * 3200 * spike_t) + 0.6 * np.sin(
        2 * np.pi * 800 * spike_t
    )
    audio_data[spike_idx_start:spike_idx_end] += combat_burst.astype(np.float32)
    # Clip to valid float32 range
    audio_data = np.clip(audio_data, -1.0, 1.0)

    # Save as 16-bit PCM WAV
    audio_wav_path = job_dir / "audio_raw.wav"
    audio_int16 = (audio_data * 32767).astype(np.int16)
    scipy.io.wavfile.write(str(audio_wav_path), sr, audio_int16)

    # Mock metadata
    mock_metadata = VideoMetadata(
        video_id="synth123456",
        canonical_url="https://www.youtube.com/watch?v=synth123456",
        title="Synthetic Apex Match",
        duration_s=duration_s,
        has_chat=False,
        has_heatmap=False,
    )

    async with get_db_connection() as db:
        # Create job
        await db.execute(
            """
            INSERT INTO jobs (id, source_url, genre, language, params_json, status, progress, created_at, updated_at)
            VALUES (?, ?, 'gaming', 'id', '{}', 'queued', 0.0, '2026-10-04T00:00:00Z', '2026-10-04T00:00:00Z')
            """,
            (job_id, mock_metadata.canonical_url),
        )
        await db.commit()

        # Run Stage 1: Validate (mocking probe_video)
        with patch("clipforge.jobs.pipeline.probe_video", new_callable=AsyncMock) as m_probe:
            m_probe.return_value = mock_metadata
            ok1 = await engine.run_stage(
                db=db,
                job_id=job_id,
                stage=StageName.VALIDATE,
                stage_fn=stage_validate,
                stage_input={"source_url": mock_metadata.canonical_url},
                progress=0.25,
            )
            assert ok1

        # Run Stage 2: Fetch Signals (mocking download_ingest_assets)
        with patch(
            "clipforge.jobs.pipeline.download_ingest_assets", new_callable=AsyncMock
        ) as m_down:
            m_down.return_value = IngestResult(
                metadata=mock_metadata,
                audio_path=str(audio_wav_path),
                chat_path=None,
                heatmap_path=None,
                disk_used_bytes=audio_wav_path.stat().st_size,
            )
            ok2 = await engine.run_stage(
                db=db,
                job_id=job_id,
                stage=StageName.FETCH_SIGNALS,
                stage_fn=stage_fetch_signals,
                stage_input={},
                progress=0.50,
            )
            assert ok2

        # Run Stage 3: Analyze Signals (Real audio feature extraction via ffmpeg)
        ok3 = await engine.run_stage(
            db=db,
            job_id=job_id,
            stage=StageName.ANALYZE_SIGNALS,
            stage_fn=stage_analyze_signals,
            stage_input={},
            progress=0.75,
        )
        assert ok3

        # Run Stage 4: Fuse Candidates (Real mathematical fusion and candidate generation)
        ok4 = await engine.run_stage(
            db=db,
            job_id=job_id,
            stage=StageName.FUSE_CANDIDATES,
            stage_fn=stage_fuse_candidates,
            stage_input={"genre": "gaming"},
            progress=0.95,
        )
        assert ok4

        await transition_job_status(db, job_id, JobStatus.AWAITING_REVIEW, progress=1.0)

        # 2. Verify Database State
        async with db.execute("SELECT status, progress FROM jobs WHERE id = ?", (job_id,)) as cur:
            row = await cur.fetchone()
            assert row[0] == JobStatus.AWAITING_REVIEW.value
            assert row[1] == 1.0

        async with db.execute("SELECT count(*) FROM candidates WHERE job_id = ?", (job_id,)) as cur:
            cand_count = (await cur.fetchone())[0]
            assert cand_count >= 1

        # 3. Verify Timeline API output
        tl = await get_timeline_for_job(job_id=job_id, db=db, data_dir=settings.data_dir)
        assert tl.duration_s == duration_s
        assert len(tl.candidates) >= 1

        # The candidate should capture the combat burst at second 30-38!
        best_cand = tl.candidates[0]
        assert best_cand.start_s <= 34.0 <= best_cand.end_s
        assert 15.0 <= best_cand.duration_s <= 60.0
