import React, { useState } from "react";
import { JobParams } from "../types";
import { ArrowRight, Film, Scissors, Sparkles, Zap } from "lucide-react";

interface JobFormProps {
  onSubmit: (
    url: string,
    genre: string,
    language: string,
    params: JobParams
  ) => Promise<void>;
  onSubmitManual?: (
    url: string,
    startTime: string,
    endTime: string,
    options: {
      title?: string;
      reframe_mode?: string;
      subtitle_style?: string;
      subtitle_position?: string;
      language?: string;
    }
  ) => Promise<void>;
  loading: boolean;
}

function parseTimestamp(ts: string): number | null {
  ts = ts.trim();
  if (!ts) return null;
  if (ts.includes(":")) {
    const parts = ts.split(":");
    if (parts.length === 2) {
      const m = parseFloat(parts[0]);
      const s = parseFloat(parts[1]);
      if (!isNaN(m) && !isNaN(s)) return m * 60 + s;
    } else if (parts.length === 3) {
      const h = parseFloat(parts[0]);
      const m = parseFloat(parts[1]);
      const s = parseFloat(parts[2]);
      if (!isNaN(h) && !isNaN(m) && !isNaN(s)) return h * 3600 + m * 60 + s;
    }
  }
  const n = parseFloat(ts);
  return isNaN(n) ? null : n;
}

function calculateDurationString(startStr: string, endStr: string): string | null {
  const s = parseTimestamp(startStr);
  const e = parseTimestamp(endStr);
  if (s !== null && e !== null && e > s) {
    const diff = Math.round((e - s) * 10) / 10;
    const m = Math.floor(diff / 60);
    const sec = Math.round((diff % 60) * 10) / 10;
    return `${m > 0 ? `${m}m ` : ""}${sec}s (${diff} dtk)`;
  }
  return null;
}

export const JobForm: React.FC<JobFormProps> = ({
  onSubmit,
  onSubmitManual,
  loading,
}) => {
  const [mode, setMode] = useState<"auto" | "manual">("auto");
  const [url, setUrl] = useState("");
  const [genre, setGenre] = useState("gaming");
  const [language, setLanguage] = useState("id");
  const [clipCount, setClipCount] = useState(5);
  const [reframeMode, setReframeMode] = useState<"blur" | "center" | "stacked">("blur");
  const [subtitleStyle, setSubtitleStyle] = useState("classic_white");
  const [subtitlePosition, setSubtitlePosition] = useState<"bottom" | "top">("bottom");
  const [error, setError] = useState<string | null>(null);

  // Manual clip state
  const [manualStartTime, setManualStartTime] = useState("");
  const [manualEndTime, setManualEndTime] = useState("");
  const [manualTitle, setManualTitle] = useState("");

  const manualDurationStr = calculateDurationString(manualStartTime, manualEndTime);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const trimmed = url.trim();
    if (!trimmed) return;

    const isValid = /^https?:\/\/(www\.)?(youtube\.com|youtu\.be)\//i.test(trimmed);
    if (!isValid) {
      setError("Link ini bukan YouTube. Tempel link youtube.com atau youtu.be.");
      return;
    }

    if (mode === "manual") {
      const startSec = parseTimestamp(manualStartTime);
      const endSec = parseTimestamp(manualEndTime);
      if (startSec === null || isNaN(startSec) || startSec < 0) {
        setError("Format waktu mulai tidak valid. Contoh: 12:35 atau 755.");
        return;
      }
      if (endSec === null || isNaN(endSec) || endSec <= startSec) {
        setError("Waktu selesai harus lebih besar dari waktu mulai. Contoh: 14:20.");
        return;
      }
      if (endSec - startSec < 1.0) {
        setError("Durasi klip minimal 1 detik.");
        return;
      }

      if (onSubmitManual) {
        onSubmitManual(trimmed, manualStartTime, manualEndTime, {
          title: manualTitle.trim() || undefined,
          reframe_mode: reframeMode,
          subtitle_style: subtitleStyle,
          subtitle_position: subtitlePosition,
          language,
        });
      } else {
        onSubmit(trimmed, "manual", language, {
          manual: true,
          start_time: manualStartTime,
          end_time: manualEndTime,
          title: manualTitle.trim() || undefined,
          reframe_mode: reframeMode,
          subtitle_style: subtitleStyle,
          subtitle_position: subtitlePosition,
        });
      }
    } else {
      onSubmit(trimmed, genre, language, {
        clip_count: clipCount,
        reframe_mode: reframeMode,
        subtitle_style: subtitleStyle,
        subtitle_position: subtitlePosition,
      });
    }
  };

  return (
    <div className="w-full">
      {/* Hero Section with Ghost Timecode */}
      <div className="relative pt-4 pb-6 overflow-hidden">
        <div className="absolute right-0 top-0 font-extrabold text-7xl md:text-9xl text-line select-none opacity-40 pointer-events-none">
          00:00:00:00
        </div>
        <div className="relative z-10">
          <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-action mb-2">
            <span className="w-2 h-2 bg-action inline-block"></span>
            YOUTUBE CLIPPER • FAST & ACCURATE
          </div>
          <h1 className="text-3xl md:text-5xl font-extrabold tracking-tight leading-none text-copy mb-3">
            {mode === "auto" ? "POTONG. PILIH. UPLOAD." : "KLIP CEPAT BERDASAR MENIT."}
          </h1>
          <p className="text-muted text-sm md:text-base max-w-2xl leading-relaxed">
            {mode === "auto"
              ? "Tempel satu link YouTube. ClipForge memindai sinyal audio RMS, chat velocity, dan replay heatmap untuk menangkap momen emas, reframe ke 9:16 vertikal, dan membakar subtitle kinetic otomatis."
              : "Ambil klip instan dengan memasukkan link dan timestamp menit mulai & selesai (contoh 12:35 ke 14:20). Bypass proses AI untuk ekstraksi secepat kilat dengan audio & video sinkron sempurna."}
          </p>
        </div>
      </div>

      {/* Mode Switch Tabs */}
      <div className="flex items-center gap-2 mb-3">
        <button
          type="button"
          onClick={() => {
            setMode("auto");
            setError(null);
          }}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-bold uppercase tracking-wider transition-colors border ${
            mode === "auto"
              ? "bg-action text-bg border-action shadow-lg"
              : "bg-surface text-muted border-line hover:text-copy"
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>AUTO CLIPPER (AI SCOUT)</span>
        </button>

        <button
          type="button"
          onClick={() => {
            setMode("manual");
            setError(null);
          }}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-bold uppercase tracking-wider transition-colors border ${
            mode === "manual"
              ? "bg-action text-bg border-action shadow-lg"
              : "bg-surface text-muted border-line hover:text-copy"
          }`}
        >
          <Scissors className="w-3.5 h-3.5" />
          <span>MANUAL CLIP (FAST TIMESTAMP)</span>
        </button>
      </div>

      {/* Clapper Slate Form */}
      <form onSubmit={handleSubmit} className="marked-frame border border-line bg-surface p-0 shadow-2xl">
        <i className="crop-mark crop-tl" />
        <i className="crop-mark crop-tr" />
        <i className="crop-mark crop-bl" />
        <i className="crop-mark crop-br" />

        {/* Slate Clapper Top Bar */}
        <div className="flex items-center justify-between px-5 py-2.5 border-b border-line bg-card/60 text-xs font-semibold text-muted tracking-wider uppercase">
          <div className="flex items-center gap-3">
            <span>SCENE 01</span>
            <span>•</span>
            <span>MODE: {mode === "auto" ? "AI HIGHLIGHT SCOUT" : "MANUAL TIMESTAMP CUT"}</span>
            <span>•</span>
            <span>SUMBER: YOUTUBE</span>
          </div>
          <div className="hidden sm:flex items-center gap-2 text-action font-mono">
            <Film className="w-3.5 h-3.5" />
            <span>24 FPS / 1080x1920</span>
          </div>
        </div>

        {/* Input & Action Row */}
        <div className="flex flex-col sm:flex-row items-stretch border-b border-line">
          <input
            type="url"
            required
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              if (error) setError(null);
            }}
            placeholder="https://youtube.com/watch?v=cLhVLsius9w..."
            className="flex-1 bg-transparent px-5 py-4 text-sm md:text-base text-copy placeholder:text-zinc-600 focus:outline-none"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading}
            className="btn-action flex items-center justify-center gap-2 px-8 py-4 text-xs md:text-sm font-bold text-bg shrink-0"
          >
            {loading ? (
              <span>MEMPROSES...</span>
            ) : mode === "auto" ? (
              <>
                <span>GENERATE CLIPS</span>
                <ArrowRight className="w-4 h-4" />
              </>
            ) : (
              <>
                <Zap className="w-4 h-4 fill-current" />
                <span>POTONG SEKARANG</span>
              </>
            )}
          </button>
        </div>

        {error && (
          <div className="px-5 py-2.5 bg-err/10 border-b border-err/30 text-err text-xs font-medium">
            {error}
          </div>
        )}

        {/* Slate Options Bar */}
        {mode === "auto" ? (
          <div className="p-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-5 bg-card/30 text-xs">
            {/* Target Count */}
            <div>
              <label className="block text-muted uppercase font-bold tracking-wider mb-2">
                Jumlah Klip
              </label>
              <div className="inline-flex border border-line bg-bg w-full">
                {[3, 5, 8, 10].map((num) => (
                  <button
                    key={num}
                    type="button"
                    onClick={() => setClipCount(num)}
                    className={`flex-1 py-1.5 font-bold transition-colors border-r border-line last:border-r-0 ${
                      clipCount === num ? "bg-action text-bg" : "text-muted hover:text-copy"
                    }`}
                  >
                    {num}
                  </button>
                ))}
              </div>
            </div>

            {/* Genre */}
            <div>
              <label className="block text-muted uppercase font-bold tracking-wider mb-2">
                Genre VOD
              </label>
              <div className="inline-flex border border-line bg-bg w-full">
                {[
                  { id: "gaming", label: "Gaming" },
                  { id: "podcast", label: "Podcast" },
                  { id: "irl", label: "IRL/Vlog" },
                ].map((g) => (
                  <button
                    key={g.id}
                    type="button"
                    onClick={() => setGenre(g.id)}
                    className={`flex-1 py-1.5 font-bold transition-colors border-r border-line last:border-r-0 ${
                      genre === g.id ? "bg-action text-bg" : "text-muted hover:text-copy"
                    }`}
                  >
                    {g.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Reframe Mode */}
            <div>
              <label className="block text-muted uppercase font-bold tracking-wider mb-2">
                Reframe 9:16
              </label>
              <select
                value={reframeMode}
                onChange={(e) => setReframeMode(e.target.value as "blur" | "center" | "stacked")}
                disabled={loading}
                className="w-full bg-bg border border-line py-1.5 px-2 text-copy focus:border-action focus:outline-none"
              >
                <option value="blur">Blur Pillarbox (Rec)</option>
                <option value="center">Center Crop</option>
                <option value="stacked">Stacked Cam/Game</option>
              </select>
            </div>

            {/* Subtitle Preset */}
            <div>
              <label className="block text-muted uppercase font-bold tracking-wider mb-2">
                Preset Subtitle
              </label>
              <select
                value={subtitleStyle}
                onChange={(e) => setSubtitleStyle(e.target.value)}
                disabled={loading}
                className="w-full bg-bg border border-line py-1.5 px-2 text-copy focus:border-action focus:outline-none"
              >
                <option value="classic_white">Classic White (Putih)</option>
                <option value="fire_orange">Fire Orange (Oranye)</option>
                <option value="hormozi_bold">Hormozi Bold (Kuning/Hijau)</option>
                <option value="mrbeast_box">MrBeast Box (Bold Gold)</option>
                <option value="neon_glow">Neon Glow (Cyan/Magenta)</option>
                <option value="minimal_clean">Minimal Clean (Putih Minimalis)</option>
                <option value="none">Tanpa Subtitle (No Subtitle)</option>
              </select>
            </div>

            {/* Subtitle Location Preset */}
            <div>
              <label className="block text-muted uppercase font-bold tracking-wider mb-2">
                Lokasi Subtitle
              </label>
              <select
                value={subtitlePosition}
                onChange={(e) => setSubtitlePosition(e.target.value as "bottom" | "top")}
                disabled={loading || subtitleStyle === "none"}
                className="w-full bg-bg border border-line py-1.5 px-2 text-copy focus:border-action focus:outline-none"
              >
                <option value="bottom">Bawah (Standar Y=1680)</option>
                <option value="top">Atas (YT Shorts Safe Y=420)</option>
              </select>
            </div>
          </div>
        ) : (
          /* Manual Clip Options Bar */
          <div className="p-5 bg-card/30 text-xs flex flex-col gap-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
              {/* Start Timestamp */}
              <div>
                <label className="block text-muted uppercase font-bold tracking-wider mb-1.5">
                  Timestamp Mulai
                </label>
                <input
                  type="text"
                  required
                  value={manualStartTime}
                  onChange={(e) => setManualStartTime(e.target.value)}
                  placeholder="Contoh: 12:35 atau 755"
                  className="w-full bg-bg border border-line py-1.5 px-2.5 text-copy font-mono focus:border-action focus:outline-none"
                />
                <span className="text-[10px] text-muted mt-1 block">Format: MM:SS, HH:MM:SS, atau detik</span>
              </div>

              {/* End Timestamp */}
              <div>
                <label className="block text-muted uppercase font-bold tracking-wider mb-1.5 flex items-center justify-between">
                  <span>Timestamp Selesai</span>
                  {manualDurationStr && (
                    <span className="text-action font-mono text-[10px] bg-action/10 px-1 py-0.5 border border-action/20">
                      {manualDurationStr}
                    </span>
                  )}
                </label>
                <input
                  type="text"
                  required
                  value={manualEndTime}
                  onChange={(e) => setManualEndTime(e.target.value)}
                  placeholder="Contoh: 14:20 atau 860"
                  className="w-full bg-bg border border-line py-1.5 px-2.5 text-copy font-mono focus:border-action focus:outline-none"
                />
                <span className="text-[10px] text-muted mt-1 block">Format: MM:SS, HH:MM:SS, atau detik</span>
              </div>

              {/* Preset Subtitle */}
              <div>
                <label className="block text-muted uppercase font-bold tracking-wider mb-1.5">
                  Preset Subtitle
                </label>
                <select
                  value={subtitleStyle}
                  onChange={(e) => setSubtitleStyle(e.target.value)}
                  disabled={loading}
                  className="w-full bg-bg border border-line py-1.5 px-2 text-copy focus:border-action focus:outline-none"
                >
                  <option value="none">Tanpa Subtitle (No Subtitle - Ekstra Cepat)</option>
                  <option value="classic_white">Classic White (Putih)</option>
                  <option value="fire_orange">Fire Orange (Oranye)</option>
                  <option value="hormozi_bold">Hormozi Bold (Kuning/Hijau)</option>
                  <option value="mrbeast_box">MrBeast Box (Bold Gold)</option>
                  <option value="neon_glow">Neon Glow (Cyan/Magenta)</option>
                  <option value="minimal_clean">Minimal Clean (Putih Minimalis)</option>
                </select>
                <span className="text-[10px] text-muted mt-1 block">Pilih Tanpa Subtitle untuk rendering instan</span>
              </div>

              {/* Subtitle Location Preset */}
              <div>
                <label className="block text-muted uppercase font-bold tracking-wider mb-1.5">
                  Lokasi Subtitle
                </label>
                <select
                  value={subtitlePosition}
                  onChange={(e) => setSubtitlePosition(e.target.value as "bottom" | "top")}
                  disabled={loading || subtitleStyle === "none"}
                  className="w-full bg-bg border border-line py-1.5 px-2 text-copy focus:border-action focus:outline-none"
                >
                  <option value="bottom">Bawah (Y=1680)</option>
                  <option value="top">Atas (YT Shorts Safe Y=420)</option>
                </select>
                <span className="text-[10px] text-muted mt-1 block">Preset posisi awal di video 9:16</span>
              </div>

              {/* Reframe Mode */}
              <div>
                <label className="block text-muted uppercase font-bold tracking-wider mb-1.5">
                  Reframe 9:16
                </label>
                <select
                  value={reframeMode}
                  onChange={(e) => setReframeMode(e.target.value as "blur" | "center" | "stacked")}
                  disabled={loading}
                  className="w-full bg-bg border border-line py-1.5 px-2 text-copy focus:border-action focus:outline-none"
                >
                  <option value="blur">Blur Pillarbox (Lanczos)</option>
                  <option value="center">Center Crop</option>
                  <option value="stacked">Stacked Cam/Game</option>
                </select>
                <span className="text-[10px] text-muted mt-1 block">Format video 1080x1920 Shorts/TikTok/Reels</span>
              </div>
            </div>

            {/* Optional Title */}
            <div>
              <label className="block text-muted uppercase font-bold tracking-wider mb-1.5">
                Judul Klip (Opsional)
              </label>
              <input
                type="text"
                value={manualTitle}
                onChange={(e) => setManualTitle(e.target.value)}
                placeholder="Contoh: Momen Boss Fight Epik (kosongkan untuk judul otomatis)"
                className="w-full bg-bg border border-line py-1.5 px-2.5 text-copy text-xs focus:border-action focus:outline-none"
              />
            </div>
          </div>
        )}

        {/* Footer info line */}
        <div className="flex items-center justify-between px-5 py-2.5 border-t border-line text-[11px] text-muted">
          <span>
            {mode === "auto"
              ? "VIDEO PUBLIK • MAKSIMAL 8 JAM • SIGNAL-FIRST DETECTION"
              : "FAST DIRECT EXTRACTION • ZERO AI OVERHEAD • FRAME-ACCURATE"}
          </span>
          <div className="flex items-center gap-3">
            <span>BAHASA: {language === "id" ? "INDONESIA (ID)" : "ENGLISH (EN)"}</span>
            <button
              type="button"
              onClick={() => setLanguage(language === "id" ? "en" : "id")}
              className="text-action hover:underline uppercase font-semibold"
            >
              Ganti ({language === "id" ? "EN" : "ID"})
            </button>
          </div>
        </div>
      </form>
    </div>
  );
};
