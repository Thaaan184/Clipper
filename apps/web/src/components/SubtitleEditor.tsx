import React, { useState } from "react";
import { SubtitleTrack, SubtitleWord } from "../types";
import {
  previewSubtitleFrame,
  rerenderClip,
  updateClipSubtitles,
} from "../api";
import {
  Check,
  Eye,
  FileEdit,
  Loader2,
  Palette,
  RefreshCw,
  Sparkles,
} from "lucide-react";

interface SubtitleEditorProps {
  clipId: string;
  initialTrack: SubtitleTrack;
  onClipUpdated?: () => void;
}

export const SubtitleEditor: React.FC<SubtitleEditorProps> = ({
  clipId,
  initialTrack,
  onClipUpdated,
}) => {
  const [words, setWords] = useState<SubtitleWord[]>(initialTrack.words || []);
  const [stylePreset, setStylePreset] = useState(
    initialTrack.style || "classic_white"
  );
  const [reframeMode, setReframeMode] = useState("blur");
  const [previewTime, setPreviewTime] = useState(1.0);
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string | null>(null);

  const [isSaving, setIsSaving] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isRerendering, setIsRerendering] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const handleWordChange = (idx: number, newText: string) => {
    setWords((prev) =>
      prev.map((w, i) => (i === idx ? { ...w, text: newText } : w))
    );
  };

  const handleSaveSubtitles = async () => {
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      await updateClipSubtitles(clipId, words, stylePreset);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      alert(`Gagal menyimpan subtitle: ${err}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handlePreviewFrame = async () => {
    setIsPreviewing(true);
    try {
      const blob = await previewSubtitleFrame(
        clipId,
        previewTime,
        stylePreset,
        reframeMode,
        words
      );
      if (previewBlobUrl) {
        URL.revokeObjectURL(previewBlobUrl);
      }
      const url = URL.createObjectURL(blob);
      setPreviewBlobUrl(url);
    } catch (err) {
      alert(`Gagal render frame preview: ${err}`);
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleRerender = async () => {
    if (
      !confirm(
        "Re-render video final dengan revisi subtitle ini sekarang?"
      )
    ) {
      return;
    }
    setIsRerendering(true);
    try {
      await rerenderClip(clipId);
      alert("Re-render berhasil! Video telah diperbarui.");
      if (onClipUpdated) onClipUpdated();
    } catch (err) {
      alert(`Gagal re-render: ${err}`);
    } finally {
      setIsRerendering(false);
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-6 shadow-xl flex flex-col gap-6">
      <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
        <div className="flex items-center gap-2">
          <FileEdit className="w-5 h-5 text-orange-500" />
          <h3 className="font-bold text-white text-base">
            Kinetic Subtitle & Style Editor
          </h3>
        </div>
        <span className="text-xs px-2.5 py-0.5 rounded-full font-mono bg-zinc-800 text-zinc-300">
          Rev #{initialTrack.revision}
        </span>
      </div>

      {/* Settings Bar */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1.5 flex items-center gap-1.5">
            <Palette className="w-3.5 h-3.5 text-orange-400" />
            Preset Style ASS
          </label>
          <select
            value={stylePreset}
            onChange={(e) => setStylePreset(e.target.value)}
            className="w-full px-3 py-2 bg-zinc-950 border border-zinc-700 rounded-lg text-white text-xs focus:outline-none focus:border-orange-500"
          >
            <option value="classic_white">Classic White</option>
            <option value="hormozi_bold">Hormozi Bold (Kuning)</option>
            <option value="fire_orange">Fire Orange</option>
            <option value="mrbeast_box">MrBeast Box</option>
            <option value="neon_glow">Neon Glow (Cyan)</option>
            <option value="minimal_clean">Minimal Clean</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1.5">
            Mode Reframe
          </label>
          <select
            value={reframeMode}
            onChange={(e) => setReframeMode(e.target.value)}
            className="w-full px-3 py-2 bg-zinc-950 border border-zinc-700 rounded-lg text-white text-xs focus:outline-none focus:border-orange-500"
          >
            <option value="blur">Blur Pillarbox (Lanczos)</option>
            <option value="center">Center Crop</option>
            <option value="stacked">Stacked Cam/Game</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-semibold uppercase tracking-wider text-zinc-400 mb-1.5">
            Waktu Preview (detik)
          </label>
          <input
            type="number"
            step="0.5"
            min="0"
            value={previewTime}
            onChange={(e) => setPreviewTime(parseFloat(e.target.value) || 0)}
            className="w-full px-3 py-2 bg-zinc-950 border border-zinc-700 rounded-lg text-white text-xs font-mono"
          />
        </div>
      </div>

      {/* Main Content: Word List + WYSIWYG Frame Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Word Grid */}
        <div className="flex flex-col gap-2">
          <div className="flex justify-between items-center text-xs text-zinc-400">
            <span>Daftar Kata ASR ({words.length} kata)</span>
            <span>Ubah teks langsung di bawah</span>
          </div>

          <div className="h-96 overflow-y-auto bg-zinc-950 p-3 rounded-xl border border-zinc-800 flex flex-col gap-2 pr-1">
            {words.length === 0 ? (
              <div className="text-zinc-600 text-xs text-center py-16">
                Tidak ada transkrip kata untuk klip ini (gameplay highlight tanpa percakapan).
              </div>
            ) : (
              words.map((w, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 p-2 bg-zinc-900/70 border border-zinc-800/80 rounded-lg text-xs"
                >
                  <span className="font-mono text-[10px] text-zinc-500 w-16 shrink-0">
                    {w.start_s.toFixed(2)}s - {w.end_s.toFixed(2)}s
                  </span>
                  <input
                    type="text"
                    value={w.text}
                    onChange={(e) => handleWordChange(idx, e.target.value)}
                    className="flex-1 px-2.5 py-1 bg-zinc-950 border border-zinc-700 rounded text-white text-xs font-semibold focus:outline-none focus:border-orange-500"
                  />
                </div>
              ))
            )}
          </div>
        </div>

        {/* WYSIWYG Frame Preview */}
        <div className="flex flex-col gap-2">
          <div className="flex justify-between items-center text-xs text-zinc-400">
            <span>WYSIWYG Libass Preview Frame</span>
            <button
              onClick={handlePreviewFrame}
              disabled={isPreviewing}
              className="flex items-center gap-1.5 px-3 py-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-bold rounded-md transition-colors"
            >
              {isPreviewing ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Eye className="w-3.5 h-3.5" />
              )}
              Render Frame ({previewTime.toFixed(1)}s)
            </button>
          </div>

          <div className="h-96 bg-zinc-950 rounded-xl border border-zinc-800 flex items-center justify-center overflow-hidden relative shadow-inner">
            {previewBlobUrl ? (
              <img
                src={previewBlobUrl}
                alt="WYSIWYG Preview"
                className="h-full w-auto object-contain"
              />
            ) : (
              <div className="flex flex-col items-center gap-2 text-zinc-600 text-xs p-6 text-center">
                <Sparkles className="w-8 h-8 text-zinc-700" />
                <span>
                  Klik &ldquo;Render Frame&rdquo; untuk melihat pratinjau visual
                  subtitles dengan font dan efek warna nyata.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Action Buttons */}
      <div className="flex items-center justify-between border-t border-zinc-800 pt-4">
        <div className="flex items-center gap-3">
          <button
            onClick={handleSaveSubtitles}
            disabled={isSaving}
            className="flex items-center gap-2 px-5 py-2.5 bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white font-bold text-xs rounded-lg transition-colors shadow-md"
          >
            {isSaving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : saveSuccess ? (
              <Check className="w-4 h-4 text-green-300" />
            ) : null}
            {saveSuccess ? "Tersimpan!" : "Simpan Revisi Subtitle"}
          </button>

          <button
            onClick={handleRerender}
            disabled={isRerendering}
            className="flex items-center gap-2 px-5 py-2.5 bg-zinc-800 hover:bg-zinc-700 disabled:opacity-50 text-zinc-200 font-bold text-xs rounded-lg transition-colors border border-zinc-700"
          >
            {isRerendering ? (
              <Loader2 className="w-4 h-4 animate-spin text-orange-400" />
            ) : (
              <RefreshCw className="w-4 h-4 text-orange-400" />
            )}
            Re-render Video Final
          </button>
        </div>
      </div>
    </div>
  );
};
