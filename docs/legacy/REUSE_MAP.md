# Module Reuse Map (v1 -> v2)

| Legacy v1 Path | Target v2 Location | Status | Retrieval Command | Notes |
|---|---|---|---|---|
| `backend/services/reframe.py` | `apps/api/src/clipforge/render/reframe.py` | Concept Kept / Rewritten | `git show legacy/v1:backend/services/reframe.py` | Layout FFmpeg filters (`blur`, `center`, `stacked`) adapted with strict canvas metrics and font bounds. |
| `backend/workers/audio_analysis.py` | `apps/api/src/clipforge/signals/audio.py` | Concept Kept / Rewritten | `git show legacy/v1:backend/workers/audio_analysis.py` | Librosa energy surge logic adapted into streaming chunked PCM STFT. |
| `backend/services/subtitles.py` | `apps/api/src/clipforge/render/subtitles/ass.py` | Rewritten from scratch | `git show legacy/v1:backend/services/subtitles.py` | Rebuilt to use Pillow font measurement, strict character escaping, and single-event active word highlight. |
| `frontend/src/components/SubtitleEditorModal.tsx` | `apps/web/src/components/SubtitleEditor.tsx` | To be rebuilt in Phase 6 | `git show legacy/v1:frontend/src/components/SubtitleEditorModal.tsx` | Interaction model referenced for server-side frame preview editor. |
