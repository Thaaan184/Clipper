import React, { useState, useEffect } from "react"
import { getClipSubtitles, retryClip } from "@/lib/api"
import type { ClipInfo, SubtitleCue } from "@/lib/api"

interface SubtitleEditorModalProps {
  clip: ClipInfo
  isOpen: boolean
  onClose: () => void
  onSaveSuccess: () => void
  onToast: (msg: string) => void
}

function fmtSec(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = (sec % 60).toFixed(1)
  return `${String(m).padStart(2, "0")}:${Number(s) < 10 ? "0" : ""}${s}`
}

export default function SubtitleEditorModal({
  clip,
  isOpen,
  onClose,
  onSaveSuccess,
  onToast,
}: SubtitleEditorModalProps) {
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [cues, setCues] = useState<SubtitleCue[]>([])
  const [mode, setMode] = useState<"cues" | "raw">("cues")
  const [rawText, setRawText] = useState("")

  useEffect(() => {
    if (!isOpen) return

    let cancelled = false
    setLoading(true)

    getClipSubtitles(clip.id)
      .then((res) => {
        if (cancelled) return
        setCues(res.cues || [])
        setRawText(res.transcript || res.cues.map((c) => c.text).join("\n"))
      })
      .catch((err) => {
        if (cancelled) return
        onToast("Gagal memuat subtitle klip: " + (err instanceof Error ? err.message : String(err)))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [isOpen, clip.id])

  if (!isOpen) return null

  const handleCueChange = (index: number, field: "text" | "start" | "end", val: string | number) => {
    setCues((prev) => {
      const copy = [...prev]
      copy[index] = { ...copy[index], [field]: val }
      return copy
    })
  }

  const handleAddCue = () => {
    const last = cues[cues.length - 1]
    const nextStart = last ? Number(last.end) : 0
    const nextEnd = Math.min(clip.duration, nextStart + 3.0)
    setCues([...cues, { start: Number(nextStart.toFixed(1)), end: Number(nextEnd.toFixed(1)), text: "" }])
  }

  const handleRemoveCue = (index: number) => {
    setCues(cues.filter((_, i) => i !== index))
  }

  const handleRawTextChange = (text: string) => {
    setRawText(text)
    // Synchronize to cues: split by non-empty lines
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean)
    if (lines.length === 0) return

    const sliceDur = clip.duration / lines.length
    const newCues: SubtitleCue[] = lines.map((line, i) => ({
      start: Number((i * sliceDur).toFixed(2)),
      end: Number(((i + 1) * sliceDur).toFixed(2)),
      text: line,
    }))
    setCues(newCues)
  }

  const handleSaveAndRender = async () => {
    const validCues = cues
      .map((c) => ({
        start: Number(c.start),
        end: Number(c.end),
        text: c.text.trim(),
      }))
      .filter((c) => c.text.length > 0)

    if (validCues.length === 0) {
      onToast("Transkrip subtitle tidak boleh kosong. Tambahkan minimal satu baris teks.")
      return
    }

    setSaving(true)
    onToast(`Menerapkan transkrip subtitle baru & re-render klip ${String(clip.clip_index).padStart(2, "0")}...`)

    try {
      await retryClip(clip.id, {
        start_time: clip.start_time,
        end_time: clip.end_time,
        layout: clip.layout,
        subtitle_lang: clip.subtitle_lang && clip.subtitle_lang !== "none" ? clip.subtitle_lang : "id",
        custom_subtitles: validCues,
        custom_transcript: validCues.map((c) => c.text).join(" "),
      })
      onToast("Subtitle berhasil diperbarui! Sedang me-render ulang...")
      onSaveSuccess()
      onClose()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal menyimpan transkrip subtitle"
      onToast(msg)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 60,
        backgroundColor: "rgba(0, 0, 0, 0.88)",
        backdropFilter: "blur(4px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 16,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !saving) onClose()
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 620,
          maxHeight: "90vh",
          backgroundColor: "#141414",
          border: "1px solid #2A2A2A",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          boxShadow: "0 20px 40px rgba(0,0,0,0.8)",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "14px 18px",
            borderBottom: "1px solid #2A2A2A",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "#0A0A0A",
          }}
        >
          <div>
            <div style={{ fontSize: 10, color: "#FF6A00", fontWeight: 700, letterSpacing: "0.15em" }}>
              CLIPFORGE // SUBTITLE EDITOR
            </div>
            <div style={{ fontSize: 14, fontWeight: 800, color: "#F5F5F5", marginTop: 2 }}>
              Klip {String(clip.clip_index).padStart(2, "0")} — {clip.hook_title || "Edit Transkrip"}
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={saving}
            style={{
              background: "transparent",
              border: "1px solid #2A2A2A",
              color: "#9A9A9A",
              width: 30,
              height: 30,
              display: "grid",
              placeItems: "center",
              cursor: "pointer",
            }}
          >
            ✕
          </button>
        </div>

        {/* Tab switch */}
        <div
          style={{
            display: "flex",
            borderBottom: "1px solid #2A2A2A",
            background: "#0A0A0A",
          }}
        >
          <button
            onClick={() => setMode("cues")}
            style={{
              flex: 1,
              padding: "9px 12px",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              border: "none",
              borderBottom: mode === "cues" ? "2px solid #FF6A00" : "2px solid transparent",
              background: mode === "cues" ? "#141414" : "transparent",
              color: mode === "cues" ? "#FF6A00" : "#9A9A9A",
              cursor: "pointer",
            }}
          >
            EDIT PER BARIS ({cues.length} CUES)
          </button>
          <button
            onClick={() => {
              setRawText(cues.map((c) => c.text).join("\n"))
              setMode("raw")
            }}
            style={{
              flex: 1,
              padding: "9px 12px",
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.08em",
              border: "none",
              borderBottom: mode === "raw" ? "2px solid #FF6A00" : "2px solid transparent",
              background: mode === "raw" ? "#141414" : "transparent",
              color: mode === "raw" ? "#FF6A00" : "#9A9A9A",
              cursor: "pointer",
            }}
          >
            TEKS UTUH / RAW TRANSCRIPT
          </button>
        </div>

        {/* Body content */}
        <div style={{ padding: 18, overflowY: "auto", flex: 1 }}>
          {loading ? (
            <div style={{ textAlign: "center", padding: "40px 0", color: "#FF6A00", fontSize: 12 }}>
              MEMUAT TRANSKRIP SUBTITLE...
            </div>
          ) : mode === "cues" ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ fontSize: 11, color: "#9A9A9A", marginBottom: 4 }}>
                Koreksi kata-kata yang salah terdeteksi (gamer slang, nama orang, istilah unik). Timing dan kinetic pop-in akan otomatis disinkronkan.
              </div>

              {cues.length === 0 ? (
                <div style={{ padding: 24, textAlign: "center", border: "1px dashed #2A2A2A", color: "#666" }}>
                  Belum ada transkrip subtitle terdaftar untuk klip ini.
                </div>
              ) : (
                cues.map((cue, idx) => (
                  <div
                    key={idx}
                    style={{
                      background: "#0A0A0A",
                      border: "1px solid #2A2A2A",
                      padding: "8px 10px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                      <span style={{ fontSize: 10, color: "#FF6A00", fontWeight: 700 }}>
                        LINE #{idx + 1}
                      </span>
                      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                          <span style={{ fontSize: 9, color: "#666" }}>MULAI</span>
                          <input
                            type="number"
                            step="0.1"
                            value={cue.start}
                            onChange={(e) => handleCueChange(idx, "start", parseFloat(e.target.value) || 0)}
                            style={{
                              width: 50,
                              background: "#141414",
                              border: "1px solid #2A2A2A",
                              color: "#AAA",
                              fontSize: 10,
                              padding: "2px 4px",
                            }}
                          />
                          <span style={{ fontSize: 9, color: "#666" }}>s</span>
                        </div>
                        <span style={{ color: "#444" }}>—</span>
                        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                          <span style={{ fontSize: 9, color: "#666" }}>SELESAI</span>
                          <input
                            type="number"
                            step="0.1"
                            value={cue.end}
                            onChange={(e) => handleCueChange(idx, "end", parseFloat(e.target.value) || 0)}
                            style={{
                              width: 50,
                              background: "#141414",
                              border: "1px solid #2A2A2A",
                              color: "#AAA",
                              fontSize: 10,
                              padding: "2px 4px",
                            }}
                          />
                          <span style={{ fontSize: 9, color: "#666" }}>s</span>
                        </div>
                        <button
                          onClick={() => handleRemoveCue(idx)}
                          title="Hapus baris ini"
                          style={{
                            background: "transparent",
                            border: "none",
                            color: "#E5484D",
                            cursor: "pointer",
                            fontSize: 13,
                            padding: "0 4px",
                          }}
                        >
                          ✕
                        </button>
                      </div>
                    </div>

                    <input
                      type="text"
                      value={cue.text}
                      onChange={(e) => handleCueChange(idx, "text", e.target.value)}
                      placeholder="Tulis kalimat / kata-kata di sini..."
                      style={{
                        width: "100%",
                        background: "#141414",
                        border: "1px solid #2A2A2A",
                        color: "#F5F5F5",
                        padding: "6px 8px",
                        fontSize: 12,
                        fontWeight: 600,
                      }}
                    />
                  </div>
                ))
              )}

              <button
                onClick={handleAddCue}
                className="btn-ghost"
                style={{
                  width: "100%",
                  justifyContent: "center",
                  fontSize: 11,
                  borderStyle: "dashed",
                  marginTop: 4,
                }}
              >
                + TAMBAH BARIS SUBTITLE
              </button>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ fontSize: 11, color: "#9A9A9A" }}>
                Ketik atau tempel transkrip lengkap di bawah. Setiap baris baru (Enter) akan otomatis dijadikan satu fragmen subtitle yang terbagi rata sepanjang durasi klip ({Math.round(clip.duration)}s).
              </div>
              <textarea
                value={rawText}
                onChange={(e) => handleRawTextChange(e.target.value)}
                rows={10}
                placeholder="Contoh:&#10;Duelist kok main gamelan di Cibaduyut woy&#10;Padahal musuh udah pasang spike di site A&#10;Malah muter muter gak jelas"
                style={{
                  width: "100%",
                  background: "#0A0A0A",
                  border: "1px solid #2A2A2A",
                  color: "#F5F5F5",
                  padding: 12,
                  fontSize: 12,
                  lineHeight: 1.6,
                  fontFamily: "monospace",
                  resize: "vertical",
                }}
              />
            </div>
          )}

          {/* Viral Style Highlight Preview */}
          <div
            style={{
              marginTop: 18,
              padding: 12,
              background: "#0A0A0A",
              border: "1px solid #2A2A2A",
              display: "flex",
              flexDirection: "column",
              gap: 4,
            }}
          >
            <div style={{ fontSize: 9, color: "#9A9A9A", letterSpacing: "0.1em" }}>
              CONTOH TAMPILAN KINETIC DI DALAM VIDEO (POP-IN ORANGE HIGHLIGHT):
            </div>
            <div
              style={{
                textAlign: "center",
                padding: "10px 0",
                fontSize: 16,
                fontWeight: 900,
                textTransform: "uppercase",
                letterSpacing: "0.03em",
              }}
            >
              <span style={{ color: "#FFF", textShadow: "0 2px 4px #000" }}>DUELIST KOK </span>
              <span
                style={{
                  color: "#FF6A00",
                  textShadow: "0 2px 8px rgba(255,106,0,0.8)",
                  display: "inline-block",
                  transform: "scale(1.15)",
                }}
              >
                MAIN
              </span>
              <span style={{ color: "#FFF", textShadow: "0 2px 4px #000" }}> GAMELAN</span>
            </div>
          </div>
        </div>

        {/* Footer actions */}
        <div
          style={{
            padding: "14px 18px",
            borderTop: "1px solid #2A2A2A",
            background: "#0A0A0A",
            display: "flex",
            gap: 10,
            justifyContent: "flex-end",
          }}
        >
          <button
            className="btn-ghost"
            style={{ padding: "0 18px", fontSize: 11, height: 38 }}
            onClick={onClose}
            disabled={saving}
          >
            Batal
          </button>
          <button
            className="btn-primary"
            style={{ padding: "0 20px", fontSize: 11, height: 38 }}
            onClick={handleSaveAndRender}
            disabled={saving || loading}
          >
            {saving ? "MEMPROSES RENDER..." : "SIMPAN & BURN SUBTITLE BARU"}
          </button>
        </div>
      </div>
    </div>
  )
}
