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
    <div className="marked-frame border border-line bg-surface p-6 shadow-2xl flex flex-col md:flex-row gap-6">
      <i className="crop-mark crop-tl" />
      <i className="crop-mark crop-tr" />
      <i className="crop-mark crop-bl" />
      <i className="crop-mark crop-br" />

      {/* 9:16 Video Player with Film Perforations */}
      <div className="w-full md:w-72 shrink-0 flex flex-col items-center">
        <div className="w-full aspect-[9/16] bg-bg border-x-4 border-dashed border-line relative shadow-2xl flex items-center justify-center overflow-hidden">
          {clip.status === "done" ? (
            <video
              src={videoUrl}
              controls
              playsInline
              className="w-full h-full object-contain"
            />
          ) : (
            <div className="text-muted text-xs flex flex-col items-center gap-2">
              <Film className="w-8 h-8 animate-pulse text-action" />
              <span className="font-mono uppercase tracking-wider">RENDERING KLIP...</span>
            </div>
          )}
        </div>
      </div>

      {/* Details & Actions */}
      <div className="flex-1 flex flex-col justify-between gap-4">
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between border-b border-line pb-3">
            <div className="flex items-center gap-2">
              <Video className="w-4 h-4 text-action" />
              <h3 className="font-extrabold text-copy text-base uppercase tracking-wider">
                HASIL RENDER KLIP 9:16
              </h3>
            </div>
            <span className="text-xs px-2.5 py-0.5 border border-line bg-card font-mono text-muted">
              ID: {clip.id.slice(0, 8)}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            <div className="bg-card p-3 border border-line">
              <span className="text-muted block text-[10px] uppercase">Format & Dimensi</span>
              <span className="font-extrabold text-copy text-sm">
                {clip.width} x {clip.height} (9:16)
              </span>
            </div>
            <div className="bg-card p-3 border border-line">
              <span className="text-muted block text-[10px] uppercase">Durasi Klip</span>
              <span className="font-extrabold text-copy text-sm">
                {clip.duration_s?.toFixed(1) || "--"} detik
              </span>
            </div>
          </div>

          {/* QA Inspection Box */}
          <div className="bg-card p-4 border border-line flex flex-col gap-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-copy uppercase tracking-wider">
                AUTOMATED QA INSPECTOR (EBU R128 & SYNC)
              </span>
              <div className="flex items-center gap-1.5">
                {qaPassed ? (
                  <span className="text-xs font-bold text-green-400 flex items-center gap-1">
                    <CheckCircle className="w-3.5 h-3.5" /> PASSED
                  </span>
                ) : (
                  <span className="text-xs font-bold text-err flex items-center gap-1">
                    <XCircle className="w-3.5 h-3.5" /> FAILED
                  </span>
                )}
              </div>
            </div>

            {clip.qa?.checks && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5 pt-1 text-[10px] font-mono">
                {Object.entries(clip.qa.checks).map(([check, ok]) => (
                  <div
                    key={check}
                    className={`px-2 py-1 border flex items-center justify-between ${
                      ok
                        ? "bg-green-500/10 border-green-500/30 text-green-300"
                        : "bg-err/10 border-err/30 text-err"
                    }`}
                  >
                    <span className="truncate">{check.replace(/_/g, " ")}</span>
                    <span className="font-bold">{ok ? "✓" : "✗"}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Buttons */}
        <div className="flex flex-wrap items-center gap-3 pt-3 border-t border-line">
          {onEditSubtitles && (
            <button
              onClick={onEditSubtitles}
              className="btn-action flex items-center gap-2 px-4 py-2 text-xs font-bold text-bg"
            >
              <FileText className="w-3.5 h-3.5" />
              <span>EDIT SUBTITLE & PRESET</span>
            </button>
          )}

          <a
            href={srtUrl}
            download={`clip-${clip.id.slice(0, 8)}.srt`}
            className="btn-ghost flex items-center gap-1.5 px-3 py-2 text-xs font-bold"
          >
            <Download className="w-3.5 h-3.5" />
            <span>DOWNLOAD .SRT</span>
          </a>

          <a
            href={videoUrl}
            download={`clip-${clip.id.slice(0, 8)}.mp4`}
            className="btn-ghost flex items-center gap-1.5 px-3 py-2 text-xs font-bold"
          >
            <Download className="w-3.5 h-3.5" />
            <span>DOWNLOAD .MP4</span>
          </a>
        </div>
      </div>
    </div>
  );
};
