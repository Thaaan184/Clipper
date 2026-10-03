import React, { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import MarkedFrame from "@/components/MarkedFrame"
import { startScan, getProjects, deleteProject } from "@/lib/api"
import type { Project } from "@/lib/api"

const DURATION_OPTS = ["15–30 dtk", "30–60 dtk", "60–90 dtk"]
const DURATION_VALS = ["15-30", "30-60", "60-90"]
const COUNT_OPTS = [3, 5, 8]
const LANG_OPTS = [
  { label: "Indonesia", val: "id" },
  { label: "English", val: "en" },
  { label: "Tanpa Subtitle", val: "none" },
]
const CONTENT_TYPE_OPTS = [
  { label: "Auto Detect", val: "auto" },
  { label: "🎮 Gaming & Stream", val: "gaming" },
  { label: "🎙️ Podcast & Talk", val: "podcast" },
  { label: "📚 Edukasi & Tech", val: "education" },
  { label: "😂 Komedi & Santai", val: "comedy" },
  { label: "🔥 Motivasi & Cerita", val: "motivation" },
]
const LAYOUT_OPTS = [
  { label: "Blur BG", val: "blur" },
  { label: "Center Crop", val: "center" },
  { label: "Stacked (Cam)", val: "stacked" },
]

export default function Home() {
  const navigate = useNavigate()
  const [url, setUrl] = useState("")
  const [clipCount, setClipCount] = useState(5)
  const [durIdx, setDurIdx] = useState(1) // "30-60"
  const [contentType, setContentType] = useState("auto")
  const [lang, setLang] = useState("id")
  const [layout, setLayout] = useState("blur")
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState("")
  const [projects, setProjects] = useState<Project[]>([])

  useEffect(() => {
    getProjects().then(setProjects).catch(() => {})
  }, [])

  const handleDeleteProject = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    if (!window.confirm("Hapus proyek ini dan seluruh video klipnya?")) return
    try {
      await deleteProject(id)
      setProjects((prev) => prev.filter((p) => p.id !== id))
    } catch {
      alert("Gagal menghapus proyek")
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErr("")

    const clean = url.trim()
    const valid = /^(https?:\/\/)?((www|m)\.)?(youtube\.com\/(watch\?v=|live\/|shorts\/|embed\/)|youtu\.be\/)[\w\-]{11}/i.test(clean)
    if (!valid) {
      setErr("Link ini bukan YouTube valid. Masukkan link youtube.com/watch?v=..., youtube.com/live/..., youtube.com/shorts/..., atau youtu.be/...")
      return
    }

    setLoading(true)
    try {
      const res = await startScan({
        url: clean,
        clip_count: clipCount,
        duration_target: DURATION_VALS[durIdx],
        content_type: contentType,
        subtitle_lang: lang,
        layout,
      })
      navigate(`/processing/${res.job_id}/${res.video_id}`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Gagal memulai scan"
      setErr(msg)
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: 1240, margin: "0 auto", padding: "0 32px 80px" }}>
      {/* Hero */}
      <section style={{ position: "relative", padding: "72px 0 40px", overflow: "hidden" }}>
        {/* Background ghost timecode */}
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            right: -10,
            top: 24,
            fontSize: "clamp(60px, 12vw, 160px)",
            fontWeight: 800,
            lineHeight: 1,
            color: "#1C1C1C",
            letterSpacing: "-0.05em",
            userSelect: "none",
            pointerEvents: "none",
          }}
        >
          00:12:04:18
        </div>

        {/* H1 */}
        <h1
          style={{
            position: "relative",
            zIndex: 1,
            fontSize: "clamp(46px, 8.5vw, 108px)",
            lineHeight: 0.92,
            fontWeight: 800,
            letterSpacing: "-0.03em",
          }}
        >
          <span style={{ display: "block" }}>Potong.</span>
          <span style={{ display: "block", paddingLeft: "0.9em" }}>Pilih.</span>
          <span style={{ display: "block", paddingLeft: "1.8em", color: "#9A9A9A" }}>Upload.</span>
        </h1>

        <p
          style={{
            position: "relative",
            zIndex: 1,
            maxWidth: "48ch",
            color: "#9A9A9A",
            margin: "28px 0 36px",
            fontSize: 16,
            lineHeight: 1.6,
          }}
        >
          Tempel satu link YouTube. ClipForge mencari momen terbaik, memotongnya ke 9:16, dan
          membakar subtitle. Kamu tinggal upload.
        </p>

        {/* Slate Input */}
        <form onSubmit={handleSubmit} style={{ position: "relative", zIndex: 1 }}>
          <div className="slate">
            <div className="slate-num">01</div>
            <input
              type="text"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value)
                setErr("")
              }}
              placeholder="https://youtube.com/watch?v=..."
              aria-label="Link YouTube"
            />
            <button type="submit" className="btn-primary slate-btn" disabled={loading}>
              {loading ? "MEMULAI..." : "GENERATE CLIPS"}
              <span aria-hidden="true">→</span>
            </button>
          </div>

          {err && (
            <div style={{ color: "#E5484D", fontSize: 13, marginTop: 8, paddingLeft: 4 }}>
              {err}
            </div>
          )}

          {/* Jenis Konten Scope */}
          <div style={{ marginTop: 20 }}>
            <div style={{ color: "#9A9A9A", fontSize: 11, fontWeight: 600, letterSpacing: "0.12em", marginBottom: 8 }}>
              KATEGORI & FOKUS KONTEN
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {CONTENT_TYPE_OPTS.map((ct) => (
                <button
                  key={ct.val}
                  type="button"
                  onClick={() => {
                    setContentType(ct.val)
                    if (ct.val === "gaming" && layout === "center") setLayout("blur")
                  }}
                  style={{
                    background: contentType === ct.val ? "#FF6A00" : "#1A1A1A",
                    color: contentType === ct.val ? "#000000" : "#E0E0E0",
                    border: `1px solid ${contentType === ct.val ? "#FF6A00" : "#2A2A2A"}`,
                    padding: "8px 14px",
                    borderRadius: 2,
                    fontSize: 12,
                    fontWeight: contentType === ct.val ? 700 : 500,
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  {ct.label}
                </button>
              ))}
            </div>
          </div>

          {/* Options row */}
          <div
            style={{
              display: "flex",
              flexWrap: "wrap",
              gap: 28,
              padding: "20px 0 0",
              maxWidth: 1040,
            }}
          >
            {/* Jumlah klip */}
            <div>
              <div style={{ color: "#9A9A9A", fontSize: 11, fontWeight: 600, letterSpacing: "0.12em", marginBottom: 6 }}>
                JUMLAH KLIP
              </div>
              <div className="seg">
                {COUNT_OPTS.map((c) => (
                  <button
                    key={c}
                    type="button"
                    className={clipCount === c ? "on" : ""}
                    onClick={() => setClipCount(c)}
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>

            {/* Durasi target */}
            <div>
              <div style={{ color: "#9A9A9A", fontSize: 11, fontWeight: 600, letterSpacing: "0.12em", marginBottom: 6 }}>
                DURASI TARGET
              </div>
              <div className="seg">
                {DURATION_OPTS.map((d, i) => (
                  <button
                    key={d}
                    type="button"
                    className={durIdx === i ? "on" : ""}
                    onClick={() => setDurIdx(i)}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>

            {/* Bahasa subtitle */}
            <div>
              <div style={{ color: "#9A9A9A", fontSize: 11, fontWeight: 600, letterSpacing: "0.12em", marginBottom: 6 }}>
                BAHASA SUBTITLE
              </div>
              <div className="seg">
                {LANG_OPTS.map((l) => (
                  <button
                    key={l.val}
                    type="button"
                    className={lang === l.val ? "on" : ""}
                    onClick={() => setLang(l.val)}
                  >
                    {l.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Layout 9:16 */}
            <div>
              <div style={{ color: "#9A9A9A", fontSize: 11, fontWeight: 600, letterSpacing: "0.12em", marginBottom: 6 }}>
                LAYOUT 9:16
              </div>
              <div className="seg">
                {LAYOUT_OPTS.map((lo) => (
                  <button
                    key={lo.val}
                    type="button"
                    className={layout === lo.val ? "on" : ""}
                    onClick={() => setLayout(lo.val)}
                  >
                    {lo.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </form>
      </section>

      {/* Proyek Terakhir */}
      {projects.length > 0 && (
        <section id="proyek" style={{ marginTop: 64 }}>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "baseline",
              marginBottom: 24,
              borderBottom: "1px solid #2A2A2A",
              paddingBottom: 16,
            }}
          >
            <h2 style={{ fontSize: 22, fontWeight: 700 }}>Proyek Terakhir</h2>
            <span style={{ color: "#9A9A9A", fontSize: 12 }}>{projects.length} proyek tersimpan</span>
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
              gap: 24,
            }}
          >
            {projects.map((p) => (
              <div
                key={p.id}
                onClick={() => navigate(`/results/${p.id}`)}
                style={{ cursor: "pointer", background: "#0A0A0A", padding: 14 }}
              >
                <MarkedFrame>
                  <div
                    style={{
                      position: "relative",
                      aspectRatio: "16/9",
                      background: "#1C1C1C",
                      overflow: "hidden",
                    }}
                  >
                    {p.thumbnail && (
                      <img
                        src={p.thumbnail}
                        alt=""
                        style={{ width: "100%", height: "100%", objectFit: "cover" }}
                      />
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
                      {p.clip_count} KLIP
                    </span>
                    <span
                      style={{
                        position: "absolute",
                        bottom: 8,
                        right: 8,
                        fontSize: 10,
                        color: "#9A9A9A",
                        background: "rgba(10,10,10,0.8)",
                        padding: "1px 6px",
                      }}
                    >
                      {Math.floor((p.duration || 0) / 60)}m {(p.duration || 0) % 60}s
                    </span>
                  </div>
                  <h3
                    style={{
                      fontSize: 14,
                      fontWeight: 700,
                      marginTop: 10,
                      marginBottom: 4,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {p.title || "Untitled"}
                  </h3>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
                    <span style={{ color: "#9A9A9A", fontSize: 11 }}>
                      {p.status === "done" ? "Selesai" : p.status}
                    </span>
                    <button
                      onClick={(e) => handleDeleteProject(e, p.id)}
                      title="Hapus Proyek"
                      style={{
                        background: "transparent",
                        border: "1px solid #333",
                        color: "#FF3333",
                        padding: "3px 8px",
                        fontSize: 10,
                        fontWeight: 700,
                        cursor: "pointer",
                        borderRadius: 2,
                        textTransform: "uppercase",
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.borderColor = "#FF3333")}
                      onMouseLeave={(e) => (e.currentTarget.style.borderColor = "#333")}
                    >
                      Hapus
                    </button>
                  </div>
                </MarkedFrame>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
