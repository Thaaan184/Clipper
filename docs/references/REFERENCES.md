# Reference Repositories Analysis & Licensing

| Metadata | Details |
|---|---|
| Date | 2026-10-04 |
| Scope | Codebase analysis, architecture ideas, and licensing boundaries |

---

## 1. Inventory of References

### 1. OpenShorts
- **URL**: `https://github.com/mutonby/openshorts`
- **License**: MIT for core framework; `cloud/` directory is source-available / commercial license.
- **Rules**: **DO NOT COPY** any code from `cloud/` or any proprietary segments.
- **Architectural Concepts Studied**:
  - Dynamic scene-based layout switching (`TRACK`, `SPLIT`, `SCREENCAST`).
  - Active speaker mouth-movement delta combined with audio RMS.
  - Subtitle placement along split-screen partition boundaries to avoid face occlusion.

### 2. ClippyMe
- **URL**: `https://github.com/fralapo/clippyme`
- **License**: MIT
- **Architectural Concepts Studied**:
  - Preflight checks for disk space, toolchain health, and input sanitization.
  - Resumable stage checkpoints to survive crashes.
  - Word, sentence, and silence boundary snapping.
  - Static camera framing per scene.

### 3. jBahr's Clip Generator
- **URL**: `https://github.com/jBahrVR/jBahrs-Clip-Generator`
- **License**: Unlicensed / All Rights Reserved.
- **Rules**: **STRICTLY PROHIBITED TO COPY CODE**. Re-implement concepts independently from first principles.
- **Architectural Concepts Studied**:
  - Transient audio percussion detection (gunfire, explosions) tagged as `[ACTION: COMBAT]`.
  - Multi-track OBS audio downmix (game track + mic track).

### 4. HighlightMiner
- **URL**: `https://github.com/atr777/HighlightMiner`
- **License**: MIT / Open Source.
- **Architectural Concepts Studied**:
  - Mathematical multi-signal fusion without LLM dependency.
  - Audio excitement + reaction lexicon + Twitch/YouTube chat burst rate.
  - Human-in-the-loop review workflow (`Keep` / `Reject` / `Retime`).

### 5. autoclipnew (ClipForge pipeline)
- **URL**: `https://github.com/PIGJET/autoclipnew`
- **License**: To be verified before code reuse.
- **Architectural Concepts Studied**:
  - YouTube "most replayed" heatmap signal extraction as prior.
  - Low-bitrate audio-only extraction for rapid candidate scanning.
