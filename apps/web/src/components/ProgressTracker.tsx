import React from "react";
import { Job } from "../types";
import { AlertCircle, RefreshCw } from "lucide-react";

interface ProgressTrackerProps {
  job: Job;
  onCancel?: () => void;
  onRetry?: () => void;
}

const STAGES = [
  { id: "validating", label: "1. Ingest & Validasi", desc: "Mengekstrak metadata dan stream video." },
  { id: "fetching_signals", label: "2. Chat & Heatmap", desc: "Mengambil chat replay dan kurva heatmap penonton." },
  { id: "analyzing_signals", label: "3. Audio & VAD", desc: "Menghitung energi RMS, onset, dan aktivitas suara." },
  { id: "fusing_candidates", label: "4. Fusi Matematis", desc: "Menggabungkan sinyal dan memotong kandidat awal." },
  { id: "targeted_asr", label: "5. Whisper ASR", desc: "Transkripsi audio kata-per-kata pada kandidat." },
  { id: "scout_rerank", label: "6. LLM Scout Verdict", desc: "LLM menilai hook, relevansi, dan memberi skor." },
  { id: "awaiting_review", label: "7. Siap Review", desc: "Kandidat siap dikurasi dan disesuaikan." },
  { id: "rendering", label: "8. Render 9:16", desc: "Reframe vertikal, loudnorm EBU R128, dan subtitle." },
  { id: "done", label: "9. Selesai", desc: "Semua klip siap diunduh dan diputar." },
];

export const ProgressTracker: React.FC<ProgressTrackerProps> = ({
  job,
  onCancel,
  onRetry,
}) => {
  const isFailed = job.status === "failed";
  const isCancelled = job.status === "cancelled";
  const isDone = job.status === "done";
  const isReview = job.status === "awaiting_review";
  const isRendering = job.status === "rendering";

  const pct = Math.round(Math.max(0, Math.min(100, (job.progress || 0) * 100)));

  // Identify active stage index
  let activeIdx = 0;
  if (job.status === "created") {
    activeIdx = 0;
  } else {
    const idx = STAGES.findIndex((s) => s.id === job.status);
    if (idx !== -1) {
      activeIdx = idx;
    } else if (isReview) {
      activeIdx = 6;
    } else if (isRendering) {
      activeIdx = 7;
    } else if (isDone) {
      activeIdx = 8;
    }
  }

  const currentStageInfo = STAGES[activeIdx] || STAGES[0];

  return (
    <div className="marked-frame border border-line bg-surface p-6 shadow-2xl flex flex-col gap-6">
      <i className="crop-mark crop-tl" />
      <i className="crop-mark crop-tr" />
      <i className="crop-mark crop-bl" />
      <i className="crop-mark crop-br" />

      {/* Header bar */}
      <div className="flex items-center justify-between border-b border-line pb-4">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 bg-action" />
          <h2 className="font-extrabold text-sm md:text-base tracking-wider uppercase text-copy">
            STATUS PEMROSESAN VOD
          </h2>
          <span className="font-mono text-xs px-2.5 py-0.5 border border-line bg-card text-muted">
            JOB: {job.id.slice(0, 8)}
          </span>
        </div>

        <div className="flex items-center gap-2">
          {isFailed && onRetry && (
            <button
              onClick={onRetry}
              className="btn-action px-3 py-1 text-xs font-bold flex items-center gap-1.5"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>RETRY RENDER</span>
            </button>
          )}

          {onCancel && !isDone && !isFailed && !isCancelled && (
            <button
              onClick={onCancel}
              className="btn-ghost px-3 py-1 text-xs font-semibold text-err border-err/40 hover:border-err"
            >
              Batalkan Job
            </button>
          )}
        </div>
      </div>

      {/* Film Playhead Timeline Track */}
      <div className="relative pt-6 pb-8 border-y border-line bg-card/40 px-4">
        {/* Track Line */}
        <div className="relative h-1 bg-line w-full rounded-none">
          <div
            className={`h-full transition-all duration-300 ${
              isFailed ? "bg-err" : isDone ? "bg-green-500" : "bg-action"
            }`}
            style={{ width: `${pct}%` }}
          />

          {/* Playhead Marker */}
          <div
            className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 flex flex-col items-center pointer-events-none transition-all duration-300"
            style={{ left: `${pct}%` }}
          >
            <div className="w-3 h-3 bg-action rotate-45 border border-bg shadow-md" />
            <span className="text-[10px] font-mono text-action mt-1.5 whitespace-nowrap bg-bg px-1 border border-line">
              {pct}%
            </span>
          </div>
        </div>

        {/* Stage Cut Points */}
        <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-2 mt-8">
          {STAGES.map((st, idx) => {
            const isCompleted = isDone || idx < activeIdx || (isReview && idx <= 6);
            const isRunning = idx === activeIdx && !isDone && !isFailed;
            const isCurrentFailed = idx === activeIdx && isFailed;

            return (
              <div
                key={st.id}
                className={`text-center flex flex-col items-center gap-1.5 ${
                  isRunning
                    ? "text-action"
                    : isCompleted
                    ? "text-copy"
                    : isCurrentFailed
                    ? "text-err"
                    : "text-zinc-600"
                }`}
              >
                <div
                  className={`w-3.5 h-3.5 border transition-colors ${
                    isCompleted
                      ? "bg-copy border-copy"
                      : isRunning
                      ? "bg-action border-action animate-pulse"
                      : isCurrentFailed
                      ? "bg-err border-err"
                      : "bg-surface border-line"
                  }`}
                />
                <span className="text-[11px] font-semibold leading-tight line-clamp-2">
                  {st.label}
                </span>
                <span className="text-[9px] uppercase tracking-wider text-muted hidden sm:inline">
                  {isCompleted
                    ? "SELESAI"
                    : isRunning
                    ? "BERJALAN"
                    : isCurrentFailed
                    ? "GAGAL"
                    : "MENUNGGU"}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Giant Percentage & Stage Status Block */}
      <div className="grid grid-cols-1 sm:grid-cols-[auto_1fr] items-center gap-6 p-6 border border-line bg-card/60">
        <div className="font-extrabold text-7xl md:text-8xl text-action leading-none tabular-nums min-w-[2.2ch]">
          {pct}
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xs uppercase font-mono tracking-wider text-muted">
              TAHAP {activeIdx + 1} DARI {STAGES.length}
            </span>
            <span className="text-muted">•</span>
            <span
              className={`text-xs uppercase font-bold px-2 py-0.5 border ${
                isFailed
                  ? "border-err/40 text-err bg-err/10"
                  : isDone
                  ? "border-green-500/40 text-green-400 bg-green-500/10"
                  : isReview
                  ? "border-action/40 text-action bg-action/10"
                  : "border-line text-copy bg-bg"
              }`}
            >
              {job.status.replace("_", " ")}
            </span>
          </div>

          <h3 className="text-xl md:text-2xl font-bold text-copy">
            {isFailed
              ? "Eksekusi Render Mengalami Hambatan"
              : isDone
              ? "Semua Klip Selesai Dirender!"
              : currentStageInfo.label}
          </h3>

          <p className="text-muted text-xs md:text-sm">
            {isFailed
              ? job.error_message || "Terjadi kesalahan saat memproses tahap ini."
              : currentStageInfo.desc}
          </p>

          {/* Progress bar */}
          <div className="w-full bg-bg h-2 border border-line mt-2">
            <div
              className={`h-full transition-all duration-300 ${
                isFailed ? "bg-err" : isDone ? "bg-green-500" : "bg-action"
              }`}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Error Callout */}
      {isFailed && (
        <div className="flex items-start gap-3 p-4 border border-err bg-err/10 text-err text-xs">
          <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
          <div className="flex-1">
            <div className="font-extrabold uppercase tracking-wider">
              ERROR: {job.error_code || "RENDER_FAILED"}
            </div>
            <div className="mt-1 text-copy font-mono text-[11px]">
              {job.error_message}
            </div>
            {onRetry && (
              <button
                onClick={onRetry}
                className="mt-3 btn-action px-4 py-1.5 text-xs font-bold inline-flex items-center gap-1.5"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>ULANGI RENDER SEKARANG</span>
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
