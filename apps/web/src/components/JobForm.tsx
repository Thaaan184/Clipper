import React, { useState } from "react";
import { JobParams } from "../types";
import { Play, Sparkles } from "lucide-react";

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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    onSubmit(url.trim(), genre, language, {
      clip_count: clipCount,
      reframe_mode: reframeMode,
      subtitle_style: subtitleStyle,
    });
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-5"
    >
      <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
        <Sparkles className="w-5 h-5 text-orange-500" />
        <h2 className="text-lg font-bold text-white tracking-wide">
          Input YouTube VOD / Livestream
        </h2>
      </div>

      <div>
        <label
          htmlFor="vod-url"
          className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1.5"
        >
          YouTube URL
        </label>
        <input
          id="vod-url"
          type="url"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.youtube.com/watch?v=cLhVLsius9w"
          className="w-full px-4 py-2.5 bg-zinc-950 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500 transition-colors"
          disabled={loading}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1.5">
            Genre
          </label>
          <select
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
            disabled={loading}
            className="w-full px-3 py-2 bg-zinc-950 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500"
          >
            <option value="gaming">Gaming / Esports</option>
            <option value="podcast">Podcast / Talkshow</option>
            <option value="irl">IRL / Vlog</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1.5">
            Bahasa
          </label>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            disabled={loading}
            className="w-full px-3 py-2 bg-zinc-950 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500"
          >
            <option value="id">Indonesia (id)</option>
            <option value="en">English (en)</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1.5">
            Reframe 9:16
          </label>
          <select
            value={reframeMode}
            onChange={(e) =>
              setReframeMode(e.target.value as "blur" | "center" | "stacked")
            }
            disabled={loading}
            className="w-full px-3 py-2 bg-zinc-950 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500"
          >
            <option value="blur">Blur Pillarbox (Recommended)</option>
            <option value="center">Center Crop</option>
            <option value="stacked">Stacked Cam/Game</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1.5">
            Preset Subtitle
          </label>
          <select
            value={subtitleStyle}
            onChange={(e) => setSubtitleStyle(e.target.value)}
            disabled={loading}
            className="w-full px-3 py-2 bg-zinc-950 border border-zinc-700 rounded-lg text-white text-sm focus:outline-none focus:border-orange-500"
          >
            <option value="classic_white">Classic White</option>
            <option value="hormozi_bold">Hormozi Bold (Yellow)</option>
            <option value="fire_orange">Fire Orange</option>
            <option value="mrbeast_box">MrBeast Box</option>
            <option value="neon_glow">Neon Glow (Cyan)</option>
            <option value="minimal_clean">Minimal Clean</option>
          </select>
        </div>
      </div>

      <div className="flex items-center justify-between pt-2">
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold uppercase tracking-wider text-zinc-400">
            Target Kandidat:
          </label>
          <input
            type="number"
            min={1}
            max={20}
            value={clipCount}
            onChange={(e) => setClipCount(Number(e.target.value))}
            className="w-16 px-2 py-1 bg-zinc-950 border border-zinc-700 rounded text-center text-white text-sm"
            disabled={loading}
          />
        </div>

        <button
          type="submit"
          disabled={loading || !url.trim()}
          className="flex items-center gap-2 px-6 py-2.5 bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white font-bold text-sm rounded-lg transition-all shadow-md active:scale-95"
        >
          <Play className="w-4 h-4 fill-white" />
          {loading ? "Memproses..." : "Mulai Analisis Signal-First"}
        </button>
      </div>
    </form>
  );
};
