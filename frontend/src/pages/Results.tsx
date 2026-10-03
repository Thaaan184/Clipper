import React, { useState, useEffect } from "react"
import { useParams, Link } from "react-router-dom"
import ClipCard from "@/components/ClipCard"
import { getVideo, downloadClipUrl } from "@/lib/api"
import type { VideoInfo, ClipInfo } from "@/lib/api"

type SortKey = "score" | "duration" | "time"

export default function Results() {
  const { videoId } = useParams<{ videoId: string }>()
  const [video, setVideo] = useState<VideoInfo | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>("score")
  const [toastMsg, setToastMsg] = useState("")
  const [toastVisible, setToastVisible] = useState(false)
  const [loading, setLoading] = useState(true)

  const showToast = (msg: string) => {
    setToastMsg(msg)
    setToastVisible(true)
    setTimeout(() => setToastVisible(false), 2400)
  }

  const loadData = () => {
    if (!videoId) return
    getVideo(videoId)
      .then((v) => {
        setVideo(v)
        setLoading(false)
      })
      .catch(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
  }, [videoId])

  const clips = video?.clips || []

  const sorted = [...clips].sort((a, b) => {
    if (sortKey === "score") return b.score - a.score
    if (sortKey === "duration") return b.duration - a.duration
    return a.start_time - b.start_time
  })

  const doneCount = clips.filter((c) => c.status === "done").length

  const handleDownloadAll = () => {
    const doneClips = clips.filter((c) => c.status === "done")
    if (doneClips.length === 0) {
      showToast("Belum ada klip yang selesai dirender")
      return
    }
    showToast(`Mengunduh ${doneClips.length} klip...`)
    doneClips.forEach((c, idx) => {
      setTimeout(() => {
        const a = document.createElement("a")
        a.href = downloadClipUrl(c.id)
        a.download = `clip_${c.clip_index}_${c.id.slice(0, 8)}.mp4`
        a.click()
      }, idx * 400)
    })
  }

  return (
    <div style={{ maxWidth: 1240, margin: "0 auto", padding: "0 32px 80px" }}>
      {/* Toast */}
      {toastVisible && <div className="toast">{toastMsg}</div>}

      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-end",
          gap: 24,
          flexWrap: "wrap",
          margin: "48px 0 28px",
        }}
      >
        <div>
          <h2 style={{ fontSize: "clamp(26px, 4vw, 44px)", fontWeight: 800, lineHeight: 1.05 }}>
            {loading ? "Memuat..." : `${doneCount} dari ${clips.length} klip siap upload`}
          </h2>
          <p style={{ color: "#9A9A9A", marginTop: 8, fontSize: 14 }}>
            Dari: {video?.title || "Video"}
          </p>
        </div>

        <div style={{ display: "flex", gap: 12 }}>
          <Link to="/" className="btn-ghost" style={{ height: 52 }}>
            ← Klip Video Baru
          </Link>
          <button
            className="btn-primary"
            onClick={handleDownloadAll}
            disabled={doneCount === 0}
          >
            Download Semua ({doneCount})
            <span aria-hidden="true">↓</span>
          </button>
        </div>
      </div>

      {/* Sort controls */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          marginBottom: 28,
          color: "#9A9A9A",
          fontSize: 12,
          flexWrap: "wrap",
        }}
      >
        <span>Urutkan:</span>
        <div className="seg">
          <button
            className={sortKey === "score" ? "on" : ""}
            onClick={() => setSortKey("score")}
          >
            Skor Tertinggi
          </button>
          <button
            className={sortKey === "duration" ? "on" : ""}
            onClick={() => setSortKey("duration")}
          >
            Durasi
          </button>
          <button
            className={sortKey === "time" ? "on" : ""}
            onClick={() => setSortKey("time")}
          >
            Urutan Waktu
          </button>
        </div>
      </div>

      {/* Clip Grid */}
      {loading ? (
        <div style={{ color: "#9A9A9A", padding: "60px 0", textAlign: "center" }}>
          Memuat klip...
        </div>
      ) : sorted.length === 0 ? (
        <div style={{ color: "#9A9A9A", padding: "60px 0", textAlign: "center" }}>
          Tidak ada klip ditemukan.
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
            gap: 28,
          }}
        >
          {sorted.map((clip) => (
            <ClipCard
              key={clip.id}
              clip={clip}
              onToast={showToast}
              onRetry={loadData}
            />
          ))}
        </div>
      )}
    </div>
  )
}
