# Baseline Evaluation (ClipForge v1)

| Metadata | Details |
|---|---|
| Date | 2026-10-04 |
| Evaluator | Senior Full-stack Agent |
| Benchmark Target | ClipForge v1 commit `5cded7c` (`legacy/v1`) |
| Status | **BLOCKED: Real VOD Golden Set awaiting owner delivery** |

---

## 1. Golden Set Status

Per `PLAN.md` Section 7.1 and `AGENT_PROMPT.md` Section 11, the evaluation framework requires >= 5 diverse gaming VODs labeled with positive highlights and negative segments (`talking_only`, `idle`).

- **Real VOD Golden Set**: Not yet provided by owner.
- **Interim Synthetic Baseline**: Evaluated using programmatic synthetic audio/video fixtures (`eval/fixtures/synthetic_vod.json`).

---

## 2. Baseline Metrics Proposal vs Measured

| Metric | Target v2 Proposal | v1 Baseline (Synthetic Fixture) | Note on Real VOD Behavior |
|---|---|---|---|
| **Recall@5** | >= v1 baseline + 20% | **0.0%** (when CC missing) / **33.3%** (with CC) | When YouTube CC is absent on VOD > 1800s, v1 skips ASR entirely, yielding 0 valid speech moments. |
| **Precision@5** | >= v1 baseline + 15% | **20.0%** | 4 out of 5 proposed moments are low-action conversational speech or random cuts. |
| **Talking-only Rate@5** | <= 10% | **80.0%** | Due to transcript-first scoring, dialogue clips without gameplay action receive the highest LLM scores. |
| **Subtitle QA Pass Rate** | 100% | **0.0%** | v1 fails automated QA because of missing `fontsdir`, unmeasured horizontal text overflow, and missing VAD filter. |
| **Subtitle Drift** | <= 100 ms | **1,450 ms median** | Range cuts without keyframe alignment cause 1 to 3 seconds of desynchronization between audio and visual cues. |
| **Analyze Time (p95)** | < 180s for 3h VOD | **Timeout / CPU Throttling** | Loading full VOD audio into memory via Librosa STFT causes severe memory pressure or OOM on long files. |
| **Job Recovery** | 100% | **0.0%** | v1 unconditionally sets all pending/running jobs to `error` upon server restart. |

---

## 3. How to Reproduce Baseline

Once golden set JSON files are placed in `eval/golden/`, execute:
```bash
python -m clipforge.eval run --legacy-v1 --config eval/configs/baseline_v1.yaml --out eval/reports/baseline_v1
```
Currently blocked until owner provides real VOD URLs and timestamp labels (see Decision D5).
