import React, { useState, useEffect, useRef } from "react"
import { useParams, useNavigate } from "react-router-dom"
import MarkedFrame from "@/components/MarkedFrame"
import { useSSE } from "@/hooks/useSSE"
import { getVideo } from "@/lib/api"
import type { VideoInfo } from "@/lib/api"

const STEPS = [
  { label: "1. Mengunduh video", desc: "Metadata ditarik, audio diekstrak bila diperlukan." },
  { label: "2. Transkripsi (Whisper)", desc: "Audio diubah jadi teks per kata." },
  { label: "3. Mencari momen terbaik", desc: "AI menilai tiap segmen transkrip dan memberi skor." },
  { label: "4. Memotong dan reframe", desc: "Klip dipotong dan diubah ke 9:16." },
  { label: "5. Membakar subtitle", desc: "Subtitle kinetic dirender tepat di titik potong." },
]

export default function Processing() {
  const { jobId, videoId } = useParams<{ jobId: string; videoId: string }>()
  const navigate = useNavigate()
  const { events, latest, done, error } = useSSE(jobId || null)
  const [video, setVideo] = useState<VideoInfo | null>(null)
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (videoId) {
      getVideo(videoId).then(setVideo).catch(() => {})
    }
  }, [videoId])

  useEffect(() => {
    if (done && !error && videoId) {
      setTimeout(() => navigate(`/results/${videoId}`), 1200)
    }
  }, [done, error, videoId, navigate])

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [events])

  const progress = latest?.progress || 0
  const stepIdx = Math.min(4, Math.floor(progress / 20))
  const stepInfo = STEPS[stepIdx] || STEPS[0]
  const currentMsg = latest?.message || "Memulai proses..."

  return (
    <div style={{ maxWidth: 1040, margin: "0 auto", padding: "48px 32px 80px" }}>
      {/* Source Video Info */}
      <div style={{ display: "flex", gap: 24, alignItems: "center", marginBottom: 40, flexWrap: "wrap" }}>
        <div style={{ width: 220, flexShrink: 0 }}>
          <MarkedFrame>
            <div style={{ position: "relative", aspectRatio: "16/9", background: "#1C1C1C", overflow: "hidden" }}>
              {video?.thumbnail && (
                <img src={video.thumbnail} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              )}
              <span
                style={{
                  position: "absolute",
                  top: 8,
                  left: 8,
                  fontSize: 10,
                  fontWeight: 700,
                  background: "#0A0A0A",
                  padding: "2px 6px",
                }}
              >
                SUMBER
              </span>
            </div>
          </MarkedFrame>
        </div>

        <div>
          <h2 style={{ fontSize: 24, fontWeight: 700, lineHeight: 1.25, maxWidth: "32ch" }}>
            {video?.title || "Memuat video..."}
          </h2>
          <p style={{ color: "#9A9A9A", marginTop: 8, fontSize: 13 }}>
            {video?.channel ? `${video.channel} • ` : ""}
            {video?.duration ? `${Math.floor(video.duration / 60)} menit ${video.duration % 60} detik` : ""}
          </p>
        </div>
      </div>

      {/* Timeline with Playhead */}
      <div
        style={{
          position: "relative",
          height: 120,
          margin: "24px 0 28px",
          borderTop: "1px solid #2A2A2A",
          borderBottom: "1px solid #2A2A2A",
          background: "#141414",
          overflow: "hidden",
        }}
      >
        {/* Track line */}
        <div style={{ position: "absolute", left: 0, right: 0, top: 28, height: 2, background: "#2A2A2A" }}>
          <div style={{ height: "100%", background: "#FF6A00", width: `${progress}%`, transition: "width 300ms ease" }} />
        </div>

        {/* Playhead */}
        <div
          style={{
            position: "absolute",
            top: 0,
            bottom: 0,
            left: `${progress}%`,
            width: 2,
            background: "#FF6A00",
            zIndex: 5,
            transition: "left 300ms ease",
          }}
        >
          <div
            style={{
              position: "absolute",
              top: 0,
              left: -5,
              width: 0,
              height: 0,
              borderTop: "9px solid #FF6A00",
              borderLeft: "6px solid transparent",
              borderRight: "6px solid transparent",
            }}
          />
          <em
            style={{
              position: "absolute",
              bottom: 8,
              left: 6,
              fontSize: 11,
              color: "#FF6A00",
              whiteSpace: "nowrap",
              fontStyle: "normal",
              fontWeight: 600,
            }}
          >
            {progress}%
          </em>
        </div>

        {/* Step markers */}
        {STEPS.map((s, i) => {
          const stepDone = progress > (i + 1) * 20
          const stepActive = progress >= i * 20 && progress <= (i + 1) * 20
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                top: 20,
                left: `${10 + i * 20}%`,
                transform: "translateX(-50%)",
                textAlign: "center",
                width: 110,
              }}
            >
              <div
                style={{
                  width: 16,
                  height: 16,
                  margin: "0 auto 8px",
                  background: stepDone ? "#F5F5F5" : stepActive ? "#0A0A0A" : "#141414",
                  border: `2px solid ${stepDone ? "#F5F5F5" : stepActive ? "#FF6A00" : "#2A2A2A"}`,
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  display: "block",
                  color: stepActive ? "#FF6A00" : stepDone ? "#F5F5F5" : "#9A9A9A",
                }}
              >
                {s.label.split(". ")[1]}
              </span>
            </div>
          )
        })}
      </div>

      {/* Now Box */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "auto 1fr",
          gap: 28,
          alignItems: "end",
          border: "1px solid #2A2A2A",
          padding: 24,
          background: "#141414",
          marginBottom: 20,
        }}
      >
        <div
          style={{
            fontSize: 88,
            fontWeight: 800,
            lineHeight: 0.9,
            color: error ? "#E5484D" : "#FF6A00",
            minWidth: "2.3ch",
          }}
        >
          {error ? "ERR" : progress}
        </div>

        <div>
          <h3 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>
            {error ? "Proses Gagal" : stepInfo.label.split(". ")[1]}
          </h3>
          <div className="pb-track" style={{ marginBottom: 8 }}>
            <div className="pb-fill" style={{ width: `${progress}%` }} />
          </div>
          <p style={{ color: error ? "#E5484D" : "#9A9A9A", fontSize: 13 }}>
            {error || currentMsg}
          </p>
        </div>
      </div>

      {/* Controls */}
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 20 }}>
        <button className="btn-ghost" onClick={() => navigate("/")}>
          ← Kembali ke Beranda
        </button>
        {done && !error && (
          <button className="btn-primary" onClick={() => navigate(`/results/${videoId}`)}>
            Lihat Hasil Klip →
          </button>
        )}
      </div>

      {/* Live Log */}
      <details
        open
        style={{
          border: "1px solid #2A2A2A",
          background: "#0A0A0A",
        }}
      >
        <summary
          style={{
            padding: "12px 16px",
            cursor: "pointer",
            fontWeight: 600,
            fontSize: 12,
            letterSpacing: "0.1em",
            color: "#9A9A9A",
          }}
        >
          LOG PROSES ({events.length} event)
        </summary>
        <div
          ref={logRef}
          style={{
            padding: "8px 16px 16px",
            color: "#9A9A9A",
            fontSize: 12,
            maxHeight: 180,
            overflowY: "auto",
            fontFamily: "monospace",
          }}
        >
          {events.map((ev, i) => (
            <div key={i} style={{ padding: "2px 0", color: ev.event === "error" ? "#E5484D" : "#9A9A9A" }}>
              [{ev.phase || ev.event}] {ev.message || ev.error}
            </div>
          ))}
          {events.length === 0 && <div>Menunggu koneksi ke server...</div>}
        </div>
      </details>
    </div>
  )
}
