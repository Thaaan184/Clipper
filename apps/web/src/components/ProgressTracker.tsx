import React from "react";
import { Job } from "../types";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Loader2,
  XCircle,
} from "lucide-react";

interface ProgressTrackerProps {
  job: Job;
  onCancel?: () => void;
}

const STAGES = [
  { id: "validating", label: "Ingest & Validasi" },
  { id: "fetching_signals", label: "Fetch Chat & Heatmap" },
  { id: "analyzing_signals", label: "Analisis Audio & VAD" },
  { id: "fusing_candidates", label: "Fusi Matematis" },
  { id: "targeted_asr", label: "Targeted Whisper ASR" },
  { id: "scout_rerank", label: "LLM Scout Verdict" },
  { id: "awaiting_review", label: "Siap Review" },
  { id: "rendering", label: "Render 9:16 & Subtitle" },
  { id: "done", label: "Selesai" },
];

export const ProgressTracker: React.FC<ProgressTrackerProps> = ({
  job,
  onCancel,
}) => {
  const isFailed = job.status === "failed";
  const isCancelled = job.status === "cancelled";
  const isDone = job.status === "done";
  const isReview = job.status === "awaiting_review";

  const getStageStatus = (_stageId: string, idx: number) => {
    const currentIdx = STAGES.findIndex((s) => s.id === job.status);
    if (isFailed || isCancelled) {
      if (idx === currentIdx) return "failed";
      return idx < currentIdx ? "completed" : "pending";
    }
    if (isDone) return "completed";
    if (isReview && idx <= currentIdx) return "completed";
    if (idx < currentIdx) return "completed";
    if (idx === currentIdx) return "active";
    return "pending";
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-5">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-3">
          <Clock className="w-5 h-5 text-orange-500" />
          <h3 className="font-bold text-white text-base">Status Pemrosesan Job</h3>
          <span className="text-xs px-2.5 py-0.5 rounded-full font-mono bg-zinc-800 text-zinc-300">
            {job.id.slice(0, 8)}
          </span>
        </div>

        {onCancel && !isDone && !isFailed && !isCancelled && (
          <button
            onClick={onCancel}
            className="text-xs text-red-400 hover:text-red-300 font-semibold px-3 py-1 bg-red-950/40 border border-red-900/50 rounded-lg transition-colors"
          >
            Batalkan Job
          </button>
        )}
      </div>

      {/* Progress Bar */}
      <div className="flex flex-col gap-1.5">
        <div className="flex justify-between text-xs text-zinc-400">
          <span className="font-medium capitalize">
            {job.status.replace("_", " ")}
          </span>
          <span className="font-mono font-bold text-white">
            {Math.round(job.progress * 100)}%
          </span>
        </div>
        <div className="w-full bg-zinc-950 h-2.5 rounded-full overflow-hidden border border-zinc-800">
          <div
            className={`h-full transition-all duration-300 ${
              isFailed
                ? "bg-red-500"
                : isCancelled
                  ? "bg-zinc-600"
                  : isDone
                    ? "bg-green-500"
                    : "bg-orange-500"
            }`}
            style={{ width: `${Math.max(5, Math.min(100, job.progress * 100))}%` }}
          />
        </div>
      </div>

      {/* Stage Grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2.5 pt-2">
        {STAGES.map((s, idx) => {
          const st = getStageStatus(s.id, idx);
          return (
            <div
              key={s.id}
              className={`p-2.5 rounded-xl border text-xs flex flex-col gap-1.5 transition-all ${
                st === "active"
                  ? "bg-orange-500/10 border-orange-500/40 text-orange-200"
                  : st === "completed"
                    ? "bg-zinc-950 border-zinc-800 text-zinc-300"
                    : st === "failed"
                      ? "bg-red-950/20 border-red-800 text-red-300"
                      : "bg-zinc-950/40 border-zinc-900 text-zinc-600"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-[11px] truncate">
                  {s.label}
                </span>
                {st === "active" && (
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-orange-500" />
                )}
                {st === "completed" && (
                  <CheckCircle2 className="w-3.5 h-3.5 text-green-500" />
                )}
                {st === "failed" && (
                  <XCircle className="w-3.5 h-3.5 text-red-500" />
                )}
              </div>
            </div>
          );
        })}
      </div>

      {isFailed && (
        <div className="flex items-start gap-3 p-3.5 bg-red-950/30 border border-red-850 rounded-xl text-red-300 text-xs">
          <AlertCircle className="w-4 h-4 shrink-0 text-red-400 mt-0.5" />
          <div>
            <div className="font-bold">Error: {job.error_code || "UNKNOWN_ERROR"}</div>
            <div className="mt-0.5 text-red-200">{job.error_message}</div>
          </div>
        </div>
      )}
    </div>
  );
};
