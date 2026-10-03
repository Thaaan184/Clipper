# Learnings & Root Cause Verification (ClipForge v1 -> v2)

| Metadata | Details |
|---|---|
| Date | 2026-10-04 |
| Scope | Code verification of hypotheses G1-G4 and H3a-H3h against ClipForge v1 code |

---

## 1. Owner Symptoms & Hypotheses Verification (G1 - G4)

### G1: Selection is overly dependent on transcripts/CC
- **Status**: **CONFIRMED**
- **Evidence in Code**:
  - `backend/workers/ingest.py` lines 92–104: If video duration > 1800s and YouTube has no CC, audio download is skipped and transcript is set to empty string `""`.
  - `backend/workers/ingest.py` lines 112–120: Audio spike detection is skipped for duration > 3600s (`duration <= 3600`).
  - `backend/services/llm.py` lines 128–137: When transcript is empty and audio spikes are empty, prompt sent to LLM contains only:
    `"CATATAN: Video ini tidak memiliki CC/subtitle otomatis (siaran langsung yang baru selesai)... Video duration: N detik... Output JSON array saja."`
  - The LLM has zero factual audio or visual grounds, forcing pure hallucination of timestamps. Conversely, when CC is present, speech-heavy segments dominate because text density is high.

### G2: Clips contain idle chat / "talking-only" without action
- **Status**: **CONFIRMED**
- **Evidence in Code**:
  - `backend/services/llm.py` lines 17–28: Prompt scoring criteria (Hook Strength, Content Density, Standalone Value, Viral Potential) heavily favor grammatically structured verbal dialogue.
  - No motion detection, no VAD separation between gaming audio and voice, and no detection of idle/loading screens exists anywhere in v1.
  - Quiet gameplay moments with conversational chatter receive high scores from the LLM because transcript segments are clean and cohesive.

### G3: Subtitles broken / corrupted
- **Status**: **CONFIRMED** (See detailed H3a–H3h verification below).

### G4: "Hasil pemilihan kurang saya suka" (No Feedback Loop)
- **Status**: **CONFIRMED**
- **Evidence in Code**:
  - Database schema (`backend/db.py`) has no `feedback` table.
  - When user rejects a clip or deletes it, no telemetry or feature snapshot is preserved.
  - The system cannot adapt weights or calibrate thresholds to user preference.

---

## 2. Subtitle Root Cause Analysis (H3a - H3h)

| ID | Hypothesis | Status | Code Evidence & Root Cause |
|---|---|---|---|
| **H3a** | Time drift: `download_ranges` without `force_keyframes_at_cuts` cuts at nearest keyframe | **CONFIRMED** | `backend/workers/editor.py` line 61: `download_ranges: download_range_func(None, [(start, end)])` without `force_keyframes_at_cuts=True`. When cut does not land on keyframe, media start time shifts up to 2–5 seconds relative to Whisper ASR t=0.0. |
| **H3b** | ASS `PlayResX/Y` mismatch with 1080x1920 canvas | **REFUTED** | `backend/services/subtitles.py` lines 18–19 explicitly sets `PlayResX: 1080` and `PlayResY: 1920`. Scaling itself is correct, but line wrapping and margin issues produce the visual defect. |
| **H3c** | Font not found by libass (fallback to system font) | **CONFIRMED** | `backend/services/subtitles.py` line 24 specifies `Style: Default,DejaVu Sans...` but neither embeds the font nor provides `fontsdir` in `reframe.py` line 25 (`ass='{sub_esc}'`). If host lacks DejaVu Sans, libass silently falls back. |
| **H3d** | Filtergraph path escaping broken | **CONFIRMED** | `backend/services/reframe.py` lines 12–14: Naive replace string `replace("\\", "/").replace(":", r"\:").replace("'", r"\'")` fails if directory path contains brackets or special unicode characters. |
| **H3e** | Karaoke `\k` centisecond rounding & overlap | **REFUTED (Alternative Found)** | v1 does not use `\k` tags. Instead, it creates discrete Dialogue events per active word with `{\fscx114\fscy114\c&H0000A8FF&}` tags. However, gaps between words are bridged up to 0.4s (`w_end = next_w_start if ... < 0.4`), causing flicker. |
| **H3f** | Text not wrapped with true font metrics; horizontal overflow | **CONFIRMED** | `backend/services/subtitles.py` lines 104–128 groups words into static `CHUNK_SIZE = 4` without measuring pixel width via font glyph metrics. 4 long Indonesian words easily exceed 1080px canvas, clipping at edges. |
| **H3g** | Whisper hallucination on silence/music | **CONFIRMED** | `backend/services/subtitles.py` line 178 explicitly sets `vad_filter=False`! Whisper hallucinates repetitive loops or phantom phrases during long game silences and background music. |
| **H3h** | Special characters `{ } \` in word text break override tags | **CONFIRMED** | `backend/services/subtitles.py` line 125 interpolates `w_text` directly: `f"{active_tag}{w_text}{reset_tag}"` without escaping curly braces or backslashes. |

---

## 3. Key Takeaways for v2 Implementation

1. **Signal-first, LLM-last**: Never query the LLM without structured factual evidence. If CC is absent, extract low-bitrate audio stream and compute real RMS/onset/VAD features.
2. **Strict Timebase**: Enforce `source_s` across pipeline; cut with pre/post-roll padding, then perform precision re-encoding trim in FFmpeg to align PTS to 0.0 before Whisper ASR.
3. **Robust Subtitle Engine**:
   - Always bundle OFL fonts in `assets/fonts/` and pass `fontsdir`.
   - Measure actual text pixel width using Pillow `ImageFont` before committing to line breaks.
   - Run Whisper with `vad_filter=True`.
   - Sanitize all `{ } \` characters prior to ASS dialogue assembly.
4. **Resumable State Machine**: Store checkpoints per stage so server restarts recover cleanly rather than destroying user jobs.
