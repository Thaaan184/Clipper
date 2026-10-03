import React, { useState } from "react";
import { Candidate } from "../types";
import {
  Check,
  ChevronDown,
  ChevronUp,
  Clock,
  Play,
  Volume2,
  X,
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

  const duration = Math.max(1, currentEnd - currentStart);
  const score = Math.round(candidate.final_score * 100);

  const formatTC = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  };

  const handleSaveTiming = () => {
    const s = parseFloat(startInput);
    const e = parseFloat(endInput);
    if (!isNaN(s) && !isNaN(e) && e > s + 3) {
      onUpdateTiming(s, e);
      setIsEditing(false);
    }
  };

  const isKept = candidate.status === "kept";
  const isRejected = candidate.status === "rejected";

  return (
    <div
      onClick={onSelect}
      className={`marked-card relative p-4 bg-bg border transition-all cursor-pointer flex flex-col gap-3 shadow-lg select-none ${
        isSelected
          ? "border-action bg-surface/90 ring-1 ring-action"
          : isRejected
          ? "border-err/30 opacity-60 hover:opacity-90"
          : "border-line hover:border-action/60"
      }`}
    >
      {/* 4 Corner Crop Marks */}
      <i className="crop-mark crop-tl" />
      <i className="crop-mark crop-tr" />
      <i className="crop-mark crop-bl" />
      <i className="crop-mark crop-br" />

      {/* 9:16 Vertical Preview Frame with Film Perforations & Giant Score */}
      <div className="relative aspect-[9/10] bg-card border-x-4 border-dashed border-line overflow-hidden flex flex-col justify-between p-3">
        {/* Top bar on thumbnail */}
        <div className="flex items-center justify-between z-10">
          <span className="text-[11px] font-mono font-bold bg-bg px-2 py-0.5 border border-line text-copy">
            CLIP {String(candidate.rank).padStart(2, "0")}
          </span>
          <span
            className={`text-[10px] font-bold px-2 py-0.5 border uppercase ${
              isKept
                ? "bg-green-500/20 text-green-400 border-green-500/40"
                : isRejected
                ? "bg-err/20 text-err border-err/40"
                : "bg-action/20 text-action border-action/40"
            }`}
          >
            {candidate.status}
          </span>
        </div>

        {/* Play Button Icon */}
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="w-10 h-10 border border-action bg-bg/90 flex items-center justify-center pl-0.5 shadow-lg">
            <Play className="w-4 h-4 text-action fill-action" />
          </div>
        </div>

        {/* Hook quote in frame */}
        <div className="z-10 bg-bg/85 border border-line/60 p-2 text-center text-xs font-bold leading-snug text-copy shadow-sm">
          {candidate.hook_text ? (
            <span className="line-clamp-2">&ldquo;{candidate.hook_text}&rdquo;</span>
          ) : (
            <span className="text-muted line-clamp-1">{candidate.title || "Gameplay Highlight"}</span>
          )}
        </div>

        {/* Bottom bar on thumbnail */}
        <div className="flex items-end justify-between z-10">
          <span className="text-[11px] font-mono text-muted bg-bg/80 px-1 border border-line/50">
            {formatTC(currentStart)} - {formatTC(currentEnd)}
          </span>
        </div>

        {/* GIANT SCORE (Museo / Heavy Tabular, clipped bottom-right) */}
        <div className="absolute -right-3 -bottom-6 font-extrabold text-7xl md:text-8xl text-action/20 pointer-events-none select-none tracking-tighter leading-none">
          {score}
        </div>
      </div>

      {/* Title & Metadata */}
      <div>
        <h4 className="font-bold text-copy text-sm leading-snug line-clamp-1">
          {candidate.title || `Highlight #${candidate.rank}`}
        </h4>
        <div className="flex items-center gap-2 mt-1 text-xs text-muted font-mono">
          <span className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 text-action" />
            {duration.toFixed(1)}s
          </span>
          <span>•</span>
          <span>{currentStart.toFixed(1)}s - {currentEnd.toFixed(1)}s</span>
        </div>
      </div>

      {/* Signal Chips */}
      <div className="flex flex-wrap gap-1.5 text-[10px]">
        <span className="px-1.5 py-0.5 border border-line bg-card text-muted uppercase font-medium">
          {candidate.category.replace("_", " ")}
        </span>
        {candidate.evidence.loud_surge_db !== undefined && (
          <span className="px-1.5 py-0.5 border border-line bg-card text-muted flex items-center gap-1">
            <Volume2 className="w-3 h-3 text-action" />
            +{candidate.evidence.loud_surge_db.toFixed(1)} dB
          </span>
        )}
        {candidate.evidence.chat_velocity !== undefined && candidate.evidence.chat_velocity > 0 && (
          <span className="px-1.5 py-0.5 border border-line bg-card text-muted">
            Chat: {candidate.evidence.chat_velocity.toFixed(1)}/s
          </span>
        )}
        {candidate.flags && candidate.flags.length > 0 && (
          <span className="px-1.5 py-0.5 border border-err/40 text-err bg-err/10 font-bold">
            {candidate.flags.join(", ")}
          </span>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center justify-between border-t border-line pt-2.5 mt-1">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onUpdateStatus("kept");
            }}
            className={`px-2.5 py-1 text-xs font-bold border transition-colors flex items-center gap-1 ${
              isKept
                ? "bg-green-500 text-bg border-green-500"
                : "border-line text-copy hover:border-action"
            }`}
          >
            <Check className="w-3 h-3" />
            <span>KEEP</span>
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onUpdateStatus("rejected");
            }}
            className={`px-2.5 py-1 text-xs font-bold border transition-colors flex items-center gap-1 ${
              isRejected
                ? "bg-err text-copy border-err"
                : "border-line text-muted hover:border-err hover:text-err"
            }`}
          >
            <X className="w-3 h-3" />
            <span>REJECT</span>
          </button>
        </div>

        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            setIsEditing(!isEditing);
          }}
          className="text-xs text-muted hover:text-copy flex items-center gap-1 font-medium"
        >
          <span>Timing</span>
          {isEditing ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
      </div>

      {/* Timing Editor Popup */}
      {isEditing && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="p-3 bg-surface border border-line flex flex-col gap-2 text-xs"
        >
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[10px] text-muted block mb-1">Mulai (detik):</label>
              <input
                type="number"
                step="0.1"
                value={startInput}
                onChange={(e) => setStartInput(e.target.value)}
                className="w-full px-2 py-1 bg-card border border-line text-copy font-mono text-xs focus:border-action focus:outline-none"
              />
            </div>
            <div>
              <label className="text-[10px] text-muted block mb-1">Selesai (detik):</label>
              <input
                type="number"
                step="0.1"
                value={endInput}
                onChange={(e) => setEndInput(e.target.value)}
                className="w-full px-2 py-1 bg-card border border-line text-copy font-mono text-xs focus:border-action focus:outline-none"
              />
            </div>
          </div>
          <button
            type="button"
            onClick={handleSaveTiming}
            className="btn-action w-full py-1 text-xs font-bold text-bg mt-1"
          >
            SIMPAN BOUNDARY
          </button>
        </div>
      )}
    </div>
  );
};
