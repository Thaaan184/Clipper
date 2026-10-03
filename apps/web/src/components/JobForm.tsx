import React, { useState } from "react";
import { JobParams } from "../types";
import { ArrowRight, Film } from "lucide-react";

interface JobFormProps {
  onSubmit: (
    url: string,
    genre: string,
    language: string,
    params: JobParams
  ) => Promise<void>;
  loading: boolean;
}

export const JobForm: React.FC<JobFormProps> = ({ onSubmit, loading }) => {
  const [url, setUrl] = useState("");
  const [genre, setGenre] = useState("gaming");
  const [language, setLanguage] = useState("id");
  const [clipCount, setClipCount] = useState(5);
  const [reframeMode, setReframeMode] = useState<"blur" | "center" | "stacked">("blur");
  const [subtitleStyle, setSubtitleStyle] = useState("classic_white");
  const [error, setError] = useState<string | null>(null);

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

    onSubmit(trimmed, genre, language, {
      clip_count: clipCount,
      reframe_mode: reframeMode,
      subtitle_style: subtitleStyle,
    });
  };

  return (
    <div className="w-full">
      {/* Hero Section with Ghost Timecode */}
      <div className="relative pt-4 pb-8 overflow-hidden">
        <div className="absolute right-0 top-0 font-extrabold text-7xl md:text-9xl text-line select-none opacity-40 pointer-events-none">
          00:00:00:00
        </div>
        <div className="relative z-10">
          <div className="inline-flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-action mb-2">
            <span className="w-2 h-2 bg-action inline-block"></span>
            YOUTUBE AUTO-CLIPPER • CUT WHAT MATTERS
          </div>
          <h1 className="text-3xl md:text-5xl font-extrabold tracking-tight leading-none text-copy mb-3">
            POTONG. PILIH. UPLOAD.
          </h1>
          <p className="text-muted text-sm md:text-base max-w-2xl leading-relaxed">
            Tempel satu link YouTube. ClipForge memindai sinyal audio RMS, chat velocity, dan replay heatmap untuk menangkap momen emas, reframe ke 9:16 vertikal, dan membakar subtitle kinetic otomatis.
          </p>
        </div>
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
            <span>TAKE 01</span>
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
            ) : (
              <>
                <span>GENERATE CLIPS</span>
                <ArrowRight className="w-4 h-4" />
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
        <div className="p-5 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 bg-card/30 text-xs">
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
              <option value="classic_white">Classic White</option>
              <option value="hormozi_bold">Hormozi Bold (Yellow)</option>
              <option value="fire_orange">Fire Orange</option>
              <option value="mrbeast_box">MrBeast Box</option>
              <option value="neon_glow">Neon Glow</option>
              <option value="minimal_clean">Minimal Clean</option>
            </select>
          </div>
        </div>

        {/* Footer info line */}
        <div className="flex items-center justify-between px-5 py-2.5 border-t border-line text-[11px] text-muted">
          <span>VIDEO PUBLIK • MAKSIMAL 8 JAM • SIGNAL-FIRST DETECTION</span>
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
