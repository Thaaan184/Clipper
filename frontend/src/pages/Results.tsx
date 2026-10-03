import React, { useState, useEffect } from "react"
import { useParams, Link, useNavigate } from "react-router-dom"
import ClipCard from "@/components/ClipCard"
import { getVideo, downloadClipUrl, deleteProject, rescanVideo } from "@/lib/api"
import type { VideoInfo, ClipInfo } from "@/lib/api"

type SortKey = "score" | "duration" | "time"

export default function Results() {
  const { videoId } = useParams<{ videoId: string }>()
  const navigate = useNavigate()
  const [video, setVideo] = useState<VideoInfo | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>("score")
  const [toastMsg, setToastMsg] = useState("")
  const [toastVisible, setToastVisible] = useState(false)
  const [loading, setLoading] = useState(true)

  // Re-scout controls
  const [showRescan, setShowRescan] = useState(false)
  const [rescanCount, setRescanCount] = useState(5)
  const [rescanDur, setRescanDur] = useState("30-60")
  const [rescanContentType, setRescanContentType] = useState("auto")
  const [rescanLayout, setRescanLayout] = useState("blur")
  const [rescanLang, setRescanLang] = useState("id")
  const [rescanning, setRescanning] = useState(false)

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

  const handleDelete = async () => {
    if (!videoId) return
    if (!window.confirm("Hapus seluruh proyek ini dan semua file videonya?")) return
    try {
      await deleteProject(videoId)
      navigate("/")
    } catch {
      showToast("Gagal menghapus proyek")
    }
  }

  const handleRescan = async () => {
    if (!videoId) return
    setRescanning(true)
    showToast("Memulai analisis ulang video...")
    try {
      const res = await rescanVideo(videoId, {
        clip_count: rescanCount,
        duration_target: rescanDur,
        content_type: rescanContentType,
        layout: rescanLayout,
        subtitle_lang: rescanLang,
      })
      navigate(`/processing/${res.job_id}/${videoId}`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Gagal rescan"
      showToast(msg)
      setRescanning(false)
    }
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

        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <Link to="/" className="btn-ghost" style={{ height: 52 }}>
            ← Beranda
          </Link>
          <button
            className={showRescan ? "btn-primary" : "btn-ghost"}
            style={{ height: 52 }}
            onClick={() => setShowRescan(!showRescan)}
          >
            {showRescan ? "Tutup Re-Scout" : "⚙ Re-Scout Proyek"}
          </button>
          <button
            className="btn-primary"
            onClick={handleDownloadAll}
            disabled={doneCount === 0}
          >
            Download Semua ({doneCount})
            <span aria-hidden="true">↓</span>
          </button>
          <button
            onClick={handleDelete}
            style={{
              height: 52,
              background: "transparent",
              border: "1px solid #FF3333",
              color: "#FF3333",
              padding: "0 16px",
              fontSize: 13,
              fontWeight: 700,
              cursor: "pointer",
              borderRadius: 2,
            }}
          >
            Hapus Proyek
          </button>
        </div>
      </div>

      {/* Re-Scout Drawer */}
      {showRescan && (
        <div
          style={{
            marginBottom: 32,
            padding: 20,
            background: "#141414",
            border: "1px solid #FF6A00",
            borderRadius: 2,
          }}
        >
          <div style={{ fontSize: 13, fontWeight: 800, color: "#FF6A00", textTransform: "uppercase", marginBottom: 12 }}>
            Re-Scout Video dengan Parameter Baru
          </div>
          <p style={{ fontSize: 12, color: "#9A9A9A", marginBottom: 16 }}>
            Transkrip sudah tersimpan di database. AI akan langsung menganalisis hook baru dan merender klip tanpa perlu mengunduh ulang video.
          </p>

          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 16 }}>
            <div>
              <label style={{ fontSize: 11, color: "#9A9A9A", display: "block", marginBottom: 4 }}>
                Fokus Konten
              </label>
              <select
                value={rescanContentType}
                onChange={(e) => setRescanContentType(e.target.value)}
                style={{ width: "100%", background: "#0A0A0A", border: "1px solid #2A2A2A", color: "#F5F5F5", padding: "8px", fontSize: 12 }}
              >
                <option value="auto">Auto Detect</option>
                <option value="gaming">🎮 Gaming & Stream</option>
                <option value="podcast">🎙️ Podcast & Talk</option>
                <option value="education">📚 Edukasi & Tech</option>
                <option value="comedy">😂 Komedi & Santai</option>
                <option value="motivation">🔥 Motivasi & Cerita</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: 11, color: "#9A9A9A", display: "block", marginBottom: 4 }}>
                Target Durasi
              </label>
              <select
                value={rescanDur}
                onChange={(e) => setRescanDur(e.target.value)}
                style={{ width: "100%", background: "#0A0A0A", border: "1px solid #2A2A2A", color: "#F5F5F5", padding: "8px", fontSize: 12 }}
              >
                <option value="15-30">15–30 dtk</option>
                <option value="30-60">30–60 dtk</option>
                <option value="60-90">60–90 dtk</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: 11, color: "#9A9A9A", display: "block", marginBottom: 4 }}>
                Jumlah Klip
              </label>
              <select
                value={rescanCount}
                onChange={(e) => setRescanCount(Number(e.target.value))}
                style={{ width: "100%", background: "#0A0A0A", border: "1px solid #2A2A2A", color: "#F5F5F5", padding: "8px", fontSize: 12 }}
              >
                <option value="3">3 klip</option>
                <option value="5">5 klip</option>
                <option value="8">8 klip</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: 11, color: "#9A9A9A", display: "block", marginBottom: 4 }}>
                Layout Video
              </label>
              <select
                value={rescanLayout}
                onChange={(e) => setRescanLayout(e.target.value)}
                style={{ width: "100%", background: "#0A0A0A", border: "1px solid #2A2A2A", color: "#F5F5F5", padding: "8px", fontSize: 12 }}
              >
                <option value="blur">Blur BG (9:16)</option>
                <option value="center">Center Crop</option>
                <option value="stacked">Stacked (Cam)</option>
              </select>
            </div>

            <div>
              <label style={{ fontSize: 11, color: "#9A9A9A", display: "block", marginBottom: 4 }}>
                Bahasa Subtitle
              </label>
              <select
                value={rescanLang}
                onChange={(e) => setRescanLang(e.target.value)}
                style={{ width: "100%", background: "#0A0A0A", border: "1px solid #2A2A2A", color: "#F5F5F5", padding: "8px", fontSize: 12 }}
              >
                <option value="id">Indonesia</option>
                <option value="en">English</option>
                <option value="none">Tanpa Subtitle (No Subtitle)</option>
              </select>
            </div>
          </div>

          <div style={{ marginTop: 20, display: "flex", justifyContent: "flex-end", gap: 12 }}>
            <button
              className="btn-ghost"
              onClick={() => setShowRescan(false)}
              disabled={rescanning}
            >
              Batal
            </button>
            <button
              className="btn-primary"
              onClick={handleRescan}
              disabled={rescanning}
            >
              {rescanning ? "Memproses..." : "Mulai Re-Scout Sekarang →"}
            </button>
          </div>
        </div>
      )}

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
