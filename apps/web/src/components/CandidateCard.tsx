import React, { useState } from "react";
import { Candidate } from "../types";
import {
  Check,
  ChevronDown,
  ChevronUp,
  Clock,
  Sparkles,
  Volume2,
  X,
  Zap,
} from "lucide-react";

interface CandidateCardProps {
  candidate: Candidate;
  isSelected: boolean;
  onSelect: () => void;
  onUpdateStatus: (status: "kept" | "rejected") => void;
  onUpdateTiming: (start_s: number, end_s: number) => void;
}

export const CandidateCard: React.FC<CandidateCardProps> = ({
  candidate,
  isSelected,
  onSelect,
  onUpdateStatus,
  onUpdateTiming,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const currentStart = candidate.user_start_s ?? candidate.start_s;
  const currentEnd = candidate.user_end_s ?? candidate.end_s;

  const [startInput, setStartInput] = useState(currentStart.toFixed(1));
  const [endInput, setEndInput] = useState(currentEnd.toFixed(1));

  const duration = currentEnd - currentStart;

  const handleSaveTiming = () => {
    const s = parseFloat(startInput);
    const e = parseFloat(endInput);
    if (!isNaN(s) && !isNaN(e) && e > s + 5) {
      onUpdateTiming(s, e);
      setIsEditing(false);
    }
  };

  const getCategoryColor = (cat: string) => {
    switch (cat) {
      case "gameplay_highlight":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "funny_fail":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "talking_only":
        return "bg-red-500/10 text-red-400 border-red-500/30";
      default:
        return "bg-blue-500/10 text-blue-400 border-blue-500/30";
    }
  };

  return (
    <div
      onClick={onSelect}
      className={`p-5 rounded-2xl border transition-all cursor-pointer flex flex-col gap-4 shadow-lg ${
        isSelected
          ? "bg-zinc-850 border-orange-500 ring-1 ring-orange-500/50"
          : "bg-zinc-900 border-zinc-800 hover:border-zinc-700"
      }`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="w-7 h-7 rounded-lg bg-orange-600 text-white font-extrabold text-xs flex items-center justify-center shadow-md">
            #{candidate.rank}
          </span>
          <div>
            <h4 className="font-bold text-white text-base leading-snug">
              {candidate.title || "Momen Highlight"}
            </h4>
            <div className="flex items-center gap-2 mt-1">
              <span
                className={`text-[10px] px-2 py-0.5 rounded-full border font-semibold uppercase tracking-wider ${getCategoryColor(
                  candidate.category
                )}`}
              >
                {candidate.category.replace("_", " ")}
              </span>
              <span className="text-xs text-zinc-400 flex items-center gap-1 font-mono">
                <Clock className="w-3.5 h-3.5 text-zinc-500" />
                {currentStart.toFixed(1)}s - {currentEnd.toFixed(1)}s (
                {duration.toFixed(1)}s)
              </span>
            </div>
          </div>
        </div>

        {/* Status Badge & Score */}
        <div className="flex flex-col items-end gap-1.5 shrink-0">
          <div className="flex items-center gap-1 bg-zinc-950 px-2.5 py-1 rounded-lg border border-zinc-800">
            <Zap className="w-3.5 h-3.5 text-orange-400" />
            <span className="text-xs font-mono font-bold text-white">
              {Math.round(candidate.final_score * 100)}
            </span>
          </div>

          <span
            className={`text-[11px] font-bold px-2 py-0.5 rounded ${
              candidate.status === "kept"
                ? "bg-green-500/20 text-green-400 border border-green-500/30"
                : candidate.status === "rejected"
                  ? "bg-red-500/20 text-red-400 border border-red-500/30"
                  : candidate.status === "rendered"
                    ? "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                    : "bg-zinc-800 text-zinc-400"
            }`}
          >
            {candidate.status.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Hook & Reason */}
      <div className="bg-zinc-950 p-3 rounded-xl border border-zinc-800 text-xs flex flex-col gap-1.5">
        {candidate.hook_text && (
          <div className="flex items-center gap-1.5 text-orange-300 font-medium">
            <Sparkles className="w-3.5 h-3.5 text-orange-400 shrink-0" />
            <span>&ldquo;{candidate.hook_text}&rdquo;</span>
          </div>
        )}
        <div className="text-zinc-400 leading-relaxed text-[11px]">
          {candidate.reason || "Kandidat lolos fusi sinyal audio dan chat."}
        </div>
      </div>

      {/* Evidence Pills */}
      <div className="flex flex-wrap gap-2 text-[10px]">
        {candidate.evidence.loud_surge_db !== undefined && (
          <div className="flex items-center gap-1 px-2 py-0.5 bg-zinc-950 rounded border border-zinc-800 text-zinc-300">
            <Volume2 className="w-3 h-3 text-blue-400" />
            <span>Surge: +{candidate.evidence.loud_surge_db.toFixed(1)} dB</span>
          </div>
        )}
        {candidate.evidence.chat_velocity !== undefined && (
          <div className="flex items-center gap-1 px-2 py-0.5 bg-zinc-950 rounded border border-zinc-800 text-zinc-300">
            <span>Chat: {candidate.evidence.chat_velocity.toFixed(2)} msg/s</span>
          </div>
        )}
        {candidate.evidence.onset_density !== undefined && (
          <div className="flex items-center gap-1 px-2 py-0.5 bg-zinc-950 rounded border border-zinc-800 text-zinc-300">
            <span>Onset: {candidate.evidence.onset_density.toFixed(1)}/s</span>
          </div>
        )}
        {candidate.flags && candidate.flags.length > 0 && (
          <div className="flex items-center gap-1 px-2 py-0.5 bg-red-950/40 rounded border border-red-900/40 text-red-300 font-semibold">
            <span>Flags: {candidate.flags.join(", ")}</span>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-between border-t border-zinc-800/80 pt-3">
        <div className="flex items-center gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onUpdateStatus("kept");
            }}
            className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-400 text-xs font-semibold rounded-lg border border-emerald-600/40 transition-colors"
          >
            <Check className="w-3.5 h-3.5" />
            Approve (Keep)
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onUpdateStatus("rejected");
            }}
            className="flex items-center gap-1 px-3 py-1.5 bg-red-600/20 hover:bg-red-600/30 text-red-400 text-xs font-semibold rounded-lg border border-red-600/40 transition-colors"
          >
            <X className="w-3.5 h-3.5" />
            Reject
          </button>
        </div>

        <button
          onClick={(e) => {
            e.stopPropagation();
            setIsEditing(!isEditing);
          }}
          className="text-xs text-zinc-400 hover:text-white flex items-center gap-1"
        >
          <span>Atur Timing</span>
          {isEditing ? (
            <ChevronUp className="w-3.5 h-3.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5" />
          )}
        </button>
      </div>

      {/* Timing Editor Slider / Inputs */}
      {isEditing && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="p-3 bg-zinc-950 rounded-xl border border-zinc-800 flex flex-col gap-2.5 text-xs"
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-zinc-500 text-[10px]">Start (detik):</label>
              <input
                type="number"
                step="0.1"
                value={startInput}
                onChange={(e) => setStartInput(e.target.value)}
                className="w-24 px-2 py-1 bg-zinc-900 border border-zinc-700 rounded text-white text-xs font-mono"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-zinc-500 text-[10px]">End (detik):</label>
              <input
                type="number"
                step="0.1"
                value={endInput}
                onChange={(e) => setEndInput(e.target.value)}
                className="w-24 px-2 py-1 bg-zinc-900 border border-zinc-700 rounded text-white text-xs font-mono"
              />
            </div>
            <button
              onClick={handleSaveTiming}
              className="mt-4 px-3 py-1 bg-orange-600 hover:bg-orange-500 text-white font-bold rounded text-xs transition-colors"
            >
              Simpan
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
