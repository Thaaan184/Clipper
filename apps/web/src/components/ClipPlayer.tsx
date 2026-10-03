import React from "react";
import { Clip } from "../types";
import { getClipSrtUrl, getClipVideoUrl } from "../api";
import {
  CheckCircle,
  Download,
  FileText,
  Film,
  Video,
  XCircle,
} from "lucide-react";

interface ClipPlayerProps {
  clip: Clip;
  onEditSubtitles?: () => void;
}

export const ClipPlayer: React.FC<ClipPlayerProps> = ({
  clip,
  onEditSubtitles,
}) => {
  const videoUrl = getClipVideoUrl(clip.id);
  const srtUrl = getClipSrtUrl(clip.id);

  const qaPassed = clip.qa?.passed ?? false;

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col md:flex-row gap-6">
      {/* 9:16 Video Player Container */}
      <div className="w-full md:w-64 shrink-0 flex flex-col items-center">
        <div className="w-full aspect-[9/16] bg-black rounded-xl overflow-hidden border border-zinc-800 relative shadow-2xl flex items-center justify-center">
          {clip.status === "done" ? (
            <video
              src={videoUrl}
              controls
              playsInline
              className="w-full h-full object-contain"
            />
          ) : (
            <div className="text-zinc-500 text-xs flex flex-col items-center gap-2">
              <Film className="w-8 h-8 animate-pulse text-zinc-600" />
              <span>Rendering clip...</span>
            </div>
          )}
        </div>
      </div>

      {/* Details & Actions */}
      <div className="flex-1 flex flex-col justify-between gap-4">
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-2.5">
            <div className="flex items-center gap-2">
              <Video className="w-5 h-5 text-orange-500" />
              <h3 className="font-bold text-white text-base">
                Clip 9:16 Rendered
              </h3>
            </div>
            <span className="text-xs px-2.5 py-0.5 rounded-full font-mono bg-zinc-800 text-zinc-300">
              {clip.id.slice(0, 8)}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs">
            <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-800">
              <span className="text-zinc-500 block text-[10px]">Resolusi</span>
              <span className="font-bold text-white font-mono">
                {clip.width} x {clip.height} (9:16)
              </span>
            </div>
            <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-800">
              <span className="text-zinc-500 block text-[10px]">Durasi</span>
              <span className="font-bold text-white font-mono">
                {clip.duration_s?.toFixed(1) || "--"} detik
              </span>
            </div>
          </div>

          {/* QA Inspection Box */}
          <div className="bg-zinc-950 p-3.5 rounded-xl border border-zinc-800 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-zinc-300">
                Automated QA Inspector
              </span>
              <div className="flex items-center gap-1.5">
                {qaPassed ? (
                  <span className="text-xs font-bold text-green-400 flex items-center gap-1">
                    <CheckCircle className="w-3.5 h-3.5" /> PASSED
                  </span>
                ) : (
                  <span className="text-xs font-bold text-red-400 flex items-center gap-1">
                    <XCircle className="w-3.5 h-3.5" /> FAILED
                  </span>
                )}
              </div>
            </div>

            {clip.qa?.checks && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 pt-1 text-[10px]">
                {Object.entries(clip.qa.checks).map(([check, ok]) => (
                  <div
                    key={check}
                    className={`px-2 py-1 rounded border flex items-center justify-between ${
                      ok
                        ? "bg-green-950/20 border-green-900/40 text-green-300"
                        : "bg-red-950/20 border-red-900/40 text-red-300"
                    }`}
                  >
                    <span className="truncate">{check.replace(/_/g, " ")}</span>
                    <span>{ok ? "✓" : "✗"}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Buttons */}
        <div className="flex flex-wrap items-center gap-3 pt-2">
          {onEditSubtitles && (
            <button
              onClick={onEditSubtitles}
              className="flex items-center gap-2 px-4 py-2 bg-orange-600 hover:bg-orange-500 text-white font-semibold text-xs rounded-lg transition-colors shadow-md"
            >
              <FileText className="w-4 h-4" />
              Edit Subtitle & Preset
            </button>
          )}

          <a
            href={srtUrl}
            download={`clip-${clip.id.slice(0, 8)}.srt`}
            className="flex items-center gap-1.5 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold rounded-lg transition-colors border border-zinc-700"
          >
            <Download className="w-3.5 h-3.5" />
            Download SRT
          </a>

          <a
            href={videoUrl}
            download={`clip-${clip.id.slice(0, 8)}.mp4`}
            className="flex items-center gap-1.5 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold rounded-lg transition-colors border border-zinc-700"
          >
            <Download className="w-3.5 h-3.5" />
            Download MP4
          </a>
        </div>
      </div>
    </div>
  );
};
