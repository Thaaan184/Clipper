import React, { useMemo } from "react";
import { Candidate, TimelineData } from "../types";
import { Activity, Flame, MessageSquare, Music } from "lucide-react";

interface TimelineVisualizerProps {
  timeline: TimelineData;
  candidates: Candidate[];
  selectedCandidateId: string | null;
  onSelectCandidate: (candidateId: string) => void;
}

export const TimelineVisualizer: React.FC<TimelineVisualizerProps> = ({
  timeline,
  candidates,
  selectedCandidateId,
  onSelectCandidate,
}) => {
  const duration = timeline.duration_s || 300;

  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60);
    const s = Math.floor(secs % 60);
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  };

  const audioPath = useMemo(() => {
    const points = timeline.audio_energy;
    if (!points || points.length === 0) return "";
    const w = 1000;
    const h = 50;
    return points
      .map((p, idx) => {
        const x = (p.time_s / duration) * w;
        const y = h - p.value * h;
        return `${idx === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");
  }, [timeline.audio_energy, duration]);

  const chatPath = useMemo(() => {
    const points = timeline.chat_velocity;
    if (!points || points.length === 0) return "";
    const w = 1000;
    const h = 50;
    return points
      .map((p, idx) => {
        const x = (p.time_s / duration) * w;
        const y = h - p.value * h;
        return `${idx === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");
  }, [timeline.chat_velocity, duration]);

  const heatmapPath = useMemo(() => {
    const points = timeline.heatmap;
    if (!points || points.length === 0) return "";
    const w = 1000;
    const h = 50;
    return points
      .map((p, idx) => {
        const x = (p.time_s / duration) * w;
        const y = h - p.value * h;
        return `${idx === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(" ");
  }, [timeline.heatmap, duration]);

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-6">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-orange-500" />
          <h3 className="font-bold text-white text-base">
            Multi-Lane Signal Timeline
          </h3>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1.5 text-blue-400">
            <Music className="w-3.5 h-3.5" />
            <span>Audio Energy RMS</span>
          </div>
          <div className="flex items-center gap-1.5 text-emerald-400">
            <MessageSquare className="w-3.5 h-3.5" />
            <span>Chat Velocity</span>
          </div>
          <div className="flex items-center gap-1.5 text-amber-400">
            <Flame className="w-3.5 h-3.5" />
            <span>Replay Heatmap</span>
          </div>
        </div>
      </div>

      {/* SVG Multi-Lane Display */}
      <div className="flex flex-col gap-3">
        {/* Lane 1: Audio Energy */}
        <div className="flex flex-col gap-1">
          <div className="text-[11px] font-semibold text-zinc-400">
            Audio RMS Peak & Surge
          </div>
          <div className="w-full h-14 bg-zinc-950 rounded-lg p-1 border border-zinc-800 relative">
            <svg
              viewBox="0 0 1000 50"
              preserveAspectRatio="none"
              className="w-full h-full"
            >
              {audioPath ? (
                <path
                  d={audioPath}
                  fill="none"
                  stroke="#38bdf8"
                  strokeWidth="1.5"
                />
              ) : (
                <text
                  x="500"
                  y="28"
                  fill="#71717a"
                  fontSize="12"
                  textAnchor="middle"
                >
                  No Audio Signal Data
                </text>
              )}
            </svg>
          </div>
        </div>

        {/* Lane 2: Chat Velocity */}
        <div className="flex flex-col gap-1">
          <div className="text-[11px] font-semibold text-zinc-400">
            Chat Velocity & Hype Spikes
          </div>
          <div className="w-full h-14 bg-zinc-950 rounded-lg p-1 border border-zinc-800 relative">
            <svg
              viewBox="0 0 1000 50"
              preserveAspectRatio="none"
              className="w-full h-full"
            >
              {chatPath ? (
                <path
                  d={chatPath}
                  fill="none"
                  stroke="#34d399"
                  strokeWidth="1.5"
                />
              ) : (
                <text
                  x="500"
                  y="28"
                  fill="#71717a"
                  fontSize="12"
                  textAnchor="middle"
                >
                  Chat Replay Unavailable (VOD Mode)
                </text>
              )}
            </svg>
          </div>
        </div>

        {/* Lane 3: Replay Heatmap */}
        <div className="flex flex-col gap-1">
          <div className="text-[11px] font-semibold text-zinc-400">
            YouTube Most-Replayed Heatmap
          </div>
          <div className="w-full h-14 bg-zinc-950 rounded-lg p-1 border border-zinc-800 relative">
            <svg
              viewBox="0 0 1000 50"
              preserveAspectRatio="none"
              className="w-full h-full"
            >
              {heatmapPath ? (
                <path
                  d={heatmapPath}
                  fill="none"
                  stroke="#fbbf24"
                  strokeWidth="1.5"
                />
              ) : (
                <text
                  x="500"
                  y="28"
                  fill="#71717a"
                  fontSize="12"
                  textAnchor="middle"
                >
                  Heatmap Unavailable
                </text>
              )}
            </svg>
          </div>
        </div>

        {/* Candidate Windows Lane */}
        <div className="flex flex-col gap-1 mt-2">
          <div className="flex justify-between text-[11px] font-semibold text-zinc-400">
            <span>Proposed Candidate Highlight Windows</span>
            <span>Durasi: {formatTime(duration)}</span>
          </div>

          <div className="w-full h-10 bg-zinc-950 rounded-lg border border-zinc-800 relative overflow-hidden flex items-center">
            {candidates.map((cand) => {
              const start = cand.user_start_s ?? cand.start_s;
              const end = cand.user_end_s ?? cand.end_s;
              const leftPct = (start / duration) * 100;
              const widthPct = Math.max(1, ((end - start) / duration) * 100);
              const isSelected = cand.id === selectedCandidateId;

              const isRejected = cand.status === "rejected";
              const isKept = cand.status === "kept";

              const bgColor = isRejected
                ? "bg-red-500/30 border-red-500"
                : isKept
                  ? "bg-green-500/40 border-green-500"
                  : "bg-orange-500/40 border-orange-500";

              return (
                <button
                  key={cand.id}
                  onClick={() => onSelectCandidate(cand.id)}
                  title={`#${cand.rank} ${cand.title} (${start.toFixed(1)}s - ${end.toFixed(1)}s)`}
                  style={{
                    left: `${leftPct}%`,
                    width: `${widthPct}%`,
                  }}
                  className={`absolute h-8 rounded border transition-all cursor-pointer flex items-center justify-center text-[10px] font-bold text-white shadow-sm ${bgColor} ${
                    isSelected ? "ring-2 ring-white scale-105 z-10" : "opacity-80 hover:opacity-100"
                  }`}
                >
                  #{cand.rank}
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
