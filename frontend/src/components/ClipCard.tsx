import React, { useState, useEffect } from "react"
import QRCode from "qrcode"
import MarkedFrame from "./MarkedFrame"
import SubtitleEditorModal from "./SubtitleEditorModal"
import { downloadClipUrl, previewClipUrl, exportClipSubtitlesUrl, retryClip } from "@/lib/api"
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
  const [isPlaying, setIsPlaying] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [isEditingSubs, setIsEditingSubs] = useState(false)
  const [showQR, setShowQR] = useState(false)
  const [qrDataUrl, setQrDataUrl] = useState("")
  const [editTitle, setEditTitle] = useState(clip.hook_title)
  const [editStart, setEditStart] = useState(clip.start_time)
  const [editEnd, setEditEnd] = useState(clip.end_time)
  const [editLayout, setEditLayout] = useState(clip.layout || "blur")
  const [editLang, setEditLang] = useState(clip.subtitle_lang || "id")
  const [editStyle, setEditStyle] = useState("popin")
  const [saving, setSaving] = useState(false)

  // Escape key handler for open modals
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (showQR) setShowQR(false)
        if (isEditing) setIsEditing(false)
      }
    }
    if (showQR || isEditing) {
      window.addEventListener("keydown", handleKeyDown)
      return () => window.removeEventListener("keydown", handleKeyDown)
    }
  }, [showQR, isEditing])

  // Generate QR code locally without third-party requests
  useEffect(() => {
    if (showQR) {
      const url = window.location.origin + previewClipUrl(clip.id)
      QRCode.toDataURL(url, { width: 220, margin: 2, color: { dark: "#000000", light: "#ffffff" } })
        .then(setQrDataUrl)
        .catch(() => setQrDataUrl(""))
    }
  }, [showQR, clip.id])

  const isFail = clip.status === "error"
  const isDone = clip.status === "done"
  const isRunning = clip.status === "rendering" || clip.status === "pending"

  const handleCopyCaption = () => {
    const rawTags = clip.hashtags || []
    const tagStr = rawTags.map((t) => (t.startsWith("#") ? t : `#${t}`)).join(" ")
    const fullText = `${clip.hook_title || ""}\n\n${clip.caption || ""}\n\n${tagStr}`.trim()
    navigator.clipboard.writeText(fullText)
    onToast("✓ Caption & Hashtag disalin!")
  }

  const handleExportSubtitles = (format: "srt" | "ass") => {
    onToast(`Mengunduh subtitle .${format.toUpperCase()}...`)
    const a = document.createElement("a")
    a.href = exportClipSubtitlesUrl(clip.id, format)
    a.download = `clip_${clip.id.slice(0, 8)}.${format}`
    a.click()
  }

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

  const handleSaveEdit = async () => {
    if (editEnd <= editStart) {
      onToast("Waktu selesai harus lebih besar dari mulai")
      return
    }
    setSaving(true)
    onToast(`Memulai render ulang klip ${String(clip.clip_index).padStart(2, "0")}...`)
    try {
      await retryClip(clip.id, {
        start_time: Number(editStart),
        end_time: Number(editEnd),
        hook_title: editTitle,
        layout: editLayout,
        subtitle_lang: editLang,
        subtitle_style: editStyle,
      })
      setIsEditing(false)
      if (onRetry) onRetry()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal menyimpan editan"
      onToast(msg)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className={`clip-card-wrap ${isFail ? "fail" : ""}`} style={{ background: "#0A0A0A", padding: 14 }}>
      <MarkedFrame>
        {/* Thumbnail 9:16 / Video player */}
        <div
          onClick={() => {
            if (isDone && !isPlaying) setIsPlaying(true)
          }}
          style={{
            position: "relative",
            aspectRatio: "9/16",
            background: "#1C1C1C",
            overflow: "hidden",
            borderLeft: "7px dashed #2A2A2A",
            borderRight: "7px dashed #2A2A2A",
            cursor: isDone && !isPlaying ? "pointer" : "default",
          }}
        >
          {isPlaying && isDone ? (
            <video
              src={previewClipUrl(clip.id)}
              controls
              autoPlay
              playsInline
              style={{
                position: "absolute",
                inset: 0,
                width: "100%",
                height: "100%",
                objectFit: "cover",
                zIndex: 10,
                background: "#000",
              }}
            />
          ) : (
            <>
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
            </>
          )}
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
            <>
              <button
                className={isPlaying ? "btn-primary" : "btn-ghost"}
                style={{ flex: 1, justifyContent: "center", padding: "0 4px", fontSize: 11 }}
                disabled={!isDone}
                onClick={() => setIsPlaying(!isPlaying)}
              >
                {isPlaying ? "Tutup" : "Preview"}
              </button>
              <button
                className={isEditing ? "btn-primary" : "btn-ghost"}
                style={{ flex: 1, justifyContent: "center", padding: "0 4px", fontSize: 11 }}
                onClick={() => setIsEditing(!isEditing)}
              >
                {isEditing ? "Tutup" : "Edit"}
              </button>
              <button
                className="btn-ghost"
                style={{ flex: 1, justifyContent: "center", padding: "0 4px", fontSize: 11 }}
                onClick={() => setIsEditingSubs(true)}
                title="Edit teks transkrip subtitle klip ini"
              >
                Subtitle
              </button>
              <button
                className="btn-ghost"
                style={{ flex: 1, justifyContent: "center", padding: "0 4px", fontSize: 11 }}
                disabled={!isDone}
                onClick={handleDownload}
              >
                {isDone ? "Unduh" : "..."}
              </button>
            </>
          )}
        </div>

        {/* Row 2 Action buttons (Pro Clipper tools) */}
        {isDone && (
          <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
            <button
              className="btn-ghost"
              style={{ flex: 1.4, justifyContent: "center", padding: "0 6px", fontSize: 10, height: 30 }}
              onClick={handleCopyCaption}
              title="Salin judul hook, caption, dan hashtags siap upload ke TikTok / Reels"
            >
              📋 Salin Teks
            </button>
            <button
              className="btn-ghost"
              style={{ flex: 1, justifyContent: "center", padding: "0 6px", fontSize: 10, height: 30 }}
              onClick={() => setShowQR(true)}
              title="Scan QR Code untuk tonton / simpan video di HP"
            >
              📱 QR HP
            </button>
            <button
              className="btn-ghost"
              style={{ flex: 0.8, justifyContent: "center", padding: "0 4px", fontSize: 10, height: 30 }}
              onClick={() => handleExportSubtitles("srt")}
              title="Download file subtitle mentah .SRT untuk Premiere/CapCut"
            >
              .SRT
            </button>
            <button
              className="btn-ghost"
              style={{ flex: 0.8, justifyContent: "center", padding: "0 4px", fontSize: 10, height: 30 }}
              onClick={() => handleExportSubtitles("ass")}
              title="Download file subtitle mentah .ASS kinetic styling"
            >
              .ASS
            </button>
          </div>
        )}

        {/* Inline Edit Drawer */}
        {isEditing && (
          <div
            style={{
              marginTop: 14,
              padding: 12,
              border: "1px solid #2A2A2A",
              background: "#141414",
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
          >
            <div style={{ fontSize: 11, fontWeight: 700, color: "#FF6A00", textTransform: "uppercase" }}>
              Edit Parameter Klip
            </div>
            <div>
              <label style={{ fontSize: 10, color: "#9A9A9A", display: "block", marginBottom: 3 }}>
                Judul Hook
              </label>
              <input
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                style={{
                  width: "100%",
                  background: "#0A0A0A",
                  border: "1px solid #2A2A2A",
                  color: "#F5F5F5",
                  padding: "5px 8px",
                  fontSize: 12,
                }}
              />
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <div>
                <label style={{ fontSize: 10, color: "#9A9A9A", display: "block", marginBottom: 3 }}>
                  Mulai (dtk)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={editStart}
                  onChange={(e) => setEditStart(parseFloat(e.target.value) || 0)}
                  style={{
                    width: "100%",
                    background: "#0A0A0A",
                    border: "1px solid #2A2A2A",
                    color: "#F5F5F5",
                    padding: "5px 8px",
                    fontSize: 12,
                  }}
                />
              </div>
              <div>
                <label style={{ fontSize: 10, color: "#9A9A9A", display: "block", marginBottom: 3 }}>
                  Selesai (dtk)
                </label>
                <input
                  type="number"
                  step="0.1"
                  value={editEnd}
                  onChange={(e) => setEditEnd(parseFloat(e.target.value) || 0)}
                  style={{
                    width: "100%",
                    background: "#0A0A0A",
                    border: "1px solid #2A2A2A",
                    color: "#F5F5F5",
                    padding: "5px 8px",
                    fontSize: 12,
                  }}
                />
              </div>
            </div>

            <div style={{ fontSize: 11, color: "#9A9A9A" }}>
              Durasi: <strong style={{ color: "#F5F5F5" }}>{Math.max(0, Math.round(editEnd - editStart))} detik</strong>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
              <div>
                <label style={{ fontSize: 10, color: "#9A9A9A", display: "block", marginBottom: 3 }}>
                  Layout
                </label>
                <select
                  value={editLayout}
                  onChange={(e) => setEditLayout(e.target.value)}
                  style={{
                    width: "100%",
                    background: "#0A0A0A",
                    border: "1px solid #2A2A2A",
                    color: "#F5F5F5",
                    padding: "5px 8px",
                    fontSize: 12,
                  }}
                >
                  <option value="blur">Blur BG</option>
                  <option value="center">Center Crop</option>
                  <option value="stacked">Stacked (Cam)</option>
                  <option value="tri_split">Tri-Split (Gaming)</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: 10, color: "#9A9A9A", display: "block", marginBottom: 3 }}>
                  Subtitle
                </label>
                <select
                  value={editLang}
                  onChange={(e) => setEditLang(e.target.value)}
                  style={{
                    width: "100%",
                    background: "#0A0A0A",
                    border: "1px solid #2A2A2A",
                    color: "#F5F5F5",
                    padding: "5px 8px",
                    fontSize: 12,
                  }}
                >
                  <option value="id">Indonesia</option>
                  <option value="en">English</option>
                  <option value="none">Tanpa Subtitle</option>
                </select>
              </div>
            </div>

            <div>
              <label style={{ fontSize: 10, color: "#9A9A9A", display: "block", marginBottom: 3 }}>
                Gaya / Style Subtitle
              </label>
              <select
                value={editStyle}
                onChange={(e) => setEditStyle(e.target.value)}
                style={{
                  width: "100%",
                  background: "#0A0A0A",
                  border: "1px solid #2A2A2A",
                  color: "#F5F5F5",
                  padding: "5px 8px",
                  fontSize: 12,
                }}
              >
                <option value="popin">Viral Pop-in (Oranye/Kuning Kinetic)</option>
                <option value="hormozi">Hormozi Impact (Neon Green Bold)</option>
                <option value="minimal">Minimalist Box (Dark Translucent)</option>
              </select>
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
              <button
                className="btn-ghost"
                style={{ flex: 1, justifyContent: "center", fontSize: 11, height: 36 }}
                onClick={() => setIsEditing(false)}
                disabled={saving}
              >
                Batal
              </button>
              <button
                className="btn-primary"
                style={{ flex: 2, justifyContent: "center", fontSize: 11, height: 36 }}
                onClick={handleSaveEdit}
                disabled={saving}
              >
                {saving ? "Memproses..." : "Render Ulang Klip"}
              </button>
            </div>

            <button
              type="button"
              className="btn-ghost"
              style={{
                width: "100%",
                justifyContent: "center",
                fontSize: 11,
                borderStyle: "dashed",
                color: "#FF6A00",
                borderColor: "#FF6A00",
                marginTop: 4,
              }}
              onClick={() => {
                setIsEditing(false)
                setIsEditingSubs(true)
              }}
            >
              ✏️ KOREKSI TEKS SUBTITLE & TRANSKRIP
            </button>
          </div>
        )}

        {/* Subtitle Editor Modal */}
        <SubtitleEditorModal
          clip={clip}
          isOpen={isEditingSubs}
          onClose={() => setIsEditingSubs(false)}
          onSaveSuccess={() => {
            if (onRetry) onRetry()
          }}
          onToast={onToast}
        />
      </MarkedFrame>

      {/* Mobile QR Transfer Modal */}
      {showQR && (
        <div
          onClick={() => setShowQR(false)}
          style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.85)",
            zIndex: 9999,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 20,
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              background: "#141414",
              border: "1px solid #FF6A00",
              padding: 24,
              maxWidth: 360,
              width: "100%",
              textAlign: "center",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 16,
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 800, color: "#FF6A00", letterSpacing: "0.08em" }}>
              TRANSFER KLIP KE SMARTPHONE
            </div>
            <p style={{ fontSize: 12, color: "#9A9A9A", margin: 0, lineHeight: 1.4 }}>
              Scan QR code ini pakai kamera HP kamu untuk memutar atau simpan video langsung ke galeri HP.
            </p>
            <div style={{ background: "#FFFFFF", padding: 12, borderRadius: 4, minWidth: 220, minHeight: 220, display: "grid", placeItems: "center" }}>
              {qrDataUrl ? (
                <img
                  src={qrDataUrl}
                  alt="QR Code Klip"
                  style={{ width: 220, height: 220, display: "block" }}
                />
              ) : (
                <div style={{ color: "#222222", fontSize: 12, fontWeight: 600 }}>Menyiapkan QR...</div>
              )}
            </div>
            <div style={{ display: "flex", gap: 8, width: "100%" }}>
              <button
                className="btn-ghost"
                style={{ flex: 1, height: 40, fontSize: 11 }}
                onClick={() => {
                  navigator.clipboard.writeText(window.location.origin + previewClipUrl(clip.id))
                  onToast("✓ Link klip disalin!")
                }}
              >
                Salin Link
              </button>
              <button
                className="btn-primary"
                style={{ flex: 1, height: 40, fontSize: 11 }}
                onClick={() => setShowQR(false)}
              >
                Tutup
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
