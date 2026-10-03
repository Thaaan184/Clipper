import React from "react"
import MarkedFrame from "./MarkedFrame"
import { downloadClipUrl, retryClip } from "@/lib/api"
import type { ClipInfo } from "@/lib/api"

interface ClipCardProps {
  clip: ClipInfo
  onToast: (msg: string) => void
  onRetry?: () => void
}

function FilmPerforations({ side }: { side: "left" | "right" }) {
  return (
    <div className={`perforations ${side}`} aria-hidden="true">
      {Array.from({ length: 12 }, (_, i) => (
        <i key={i} />
      ))}
    </div>
  )
}

function fmtTime(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`
}

export default function ClipCard({ clip, onToast, onRetry }: ClipCardProps) {
  const isFail = clip.status === "error"
  const isDone = clip.status === "done"
  const isRunning = clip.status === "rendering"

  const handleDownload = () => {
    onToast(`Mengunduh klip ${String(clip.clip_index).padStart(2, "0")}...`)
    const a = document.createElement("a")
    a.href = downloadClipUrl(clip.id)
    a.download = `clip_${clip.id}.mp4`
    a.click()
  }

  const handleRetry = async () => {
    onToast(`Mengulang render klip ${String(clip.clip_index).padStart(2, "0")}...`)
    try {
      await retryClip(clip.id, clip.layout)
      if (onRetry) onRetry()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Retry gagal"
      onToast(msg)
    }
  }

  return (
    <div className={`clip-card-wrap ${isFail ? "fail" : ""}`} style={{ background: "#0A0A0A", padding: 14 }}>
      <MarkedFrame>
        {/* Thumbnail 9:16 */}
        <div
          style={{
            position: "relative",
            aspectRatio: "9/16",
            background: "#1C1C1C",
            overflow: "hidden",
            borderLeft: "7px dashed #2A2A2A",
            borderRight: "7px dashed #2A2A2A",
          }}
        >
          <FilmPerforations side="left" />

          {/* Clip label */}
          <span
            style={{
              position: "absolute",
              top: 10,
              left: 10,
              fontSize: 11,
              fontWeight: 700,
              background: "#0A0A0A",
              padding: "2px 8px",
              letterSpacing: "0.1em",
              zIndex: 4,
            }}
          >
            CLIP {String(clip.clip_index).padStart(2, "0")}
          </span>

          {/* Play icon */}
          {isDone && (
            <div
              style={{
                position: "absolute",
                top: "42%",
                left: "50%",
                transform: "translate(-50%, -50%)",
                width: 44,
                height: 44,
                border: "1px solid #FF6A00",
                background: "#0A0A0A",
                display: "grid",
                placeItems: "center",
                zIndex: 4,
              }}
            >
              <span
                style={{
                  width: 0,
                  height: 0,
                  borderTop: "7px solid transparent",
                  borderBottom: "7px solid transparent",
                  borderLeft: "11px solid #FF6A00",
                  marginLeft: 4,
                  display: "block",
                }}
              />
            </div>
          )}

          {/* Running spinner */}
          {isRunning && (
            <div
              style={{
                position: "absolute",
                top: "42%",
                left: "50%",
                transform: "translate(-50%, -50%)",
                fontSize: 11,
                color: "#FF6A00",
                fontWeight: 700,
                letterSpacing: "0.1em",
                zIndex: 4,
              }}
            >
              RENDERING...
            </div>
          )}

          {/* Hook caption preview */}
          <div
            style={{
              position: "absolute",
              left: 12,
              right: 12,
              top: "60%",
              textAlign: "center",
              fontSize: 14,
              fontWeight: 800,
              lineHeight: 1.25,
              zIndex: 4,
              color: isFail ? "#E5484D" : "#F5F5F5",
            }}
          >
            {isFail ? "Render gagal" : clip.hook_title}
          </div>

          {/* Timecode */}
          <span
            style={{
              position: "absolute",
              bottom: 10,
              left: 10,
              fontSize: 11,
              color: "#9A9A9A",
              zIndex: 4,
            }}
          >
            {fmtTime(clip.start_time)}
          </span>

          {/* Giant score */}
          <span
            style={{
              position: "absolute",
              right: -6,
              bottom: -24,
              fontSize: 120,
              fontWeight: 800,
              lineHeight: 1,
              color: isFail ? "#2A2A2A" : "#FF6A00",
              letterSpacing: "-0.07em",
              userSelect: "none",
              zIndex: 3,
            }}
          >
            {clip.score}
          </span>

          <FilmPerforations side="right" />
        </div>

        {/* Card info */}
        <h3
          style={{
            fontSize: 15,
            fontWeight: 700,
            marginTop: 14,
            marginBottom: 4,
            lineHeight: 1.25,
          }}
        >
          {clip.hook_title}
        </h3>

        <div style={{ display: "flex", gap: 14, color: "#9A9A9A", fontSize: 12, marginBottom: 8 }}>
          <span>{Math.round(clip.duration)} dtk</span>
          <span>{fmtTime(clip.start_time)}–{fmtTime(clip.end_time)}</span>
          <span style={{ textTransform: "uppercase" }}>{clip.layout}</span>
        </div>

        {/* Chips */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", minHeight: 22 }}>
          {clip.content_type && (
            <span style={{ border: "1px solid #2A2A2A", padding: "1px 8px", fontSize: 11, color: "#9A9A9A" }}>
              {clip.content_type}
            </span>
          )}
          {isFail && (
            <span style={{ border: "1px solid #E5484D", color: "#E5484D", padding: "1px 8px", fontSize: 11 }}>
              {clip.error_msg || "Render gagal"}
            </span>
          )}
        </div>

        {/* Action buttons */}
        <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
          {isFail ? (
            <button className="btn-ghost" style={{ flex: 1, justifyContent: "center" }} onClick={handleRetry}>
              Retry clip
            </button>
          ) : (
            <button
              className="btn-ghost"
              style={{ flex: 1, justifyContent: "center" }}
              disabled={!isDone}
              onClick={handleDownload}
            >
              {isDone ? "Download" : "Memproses..."}
            </button>
          )}
        </div>
      </MarkedFrame>
    </div>
  )
}
