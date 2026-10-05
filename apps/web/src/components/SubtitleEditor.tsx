import React, { useEffect, useState } from "react";
import { SubtitleTrack, SubtitleWord } from "../types";
import {
  previewSubtitleFrame,
  rerenderClip,
  saveFinishedClip,
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
  const getInitialPreset = (style: any): string => {
    if (typeof style === "string" && style.trim()) return style;
    if (style && typeof style === "object" && style.preset) return String(style.preset);
    return "classic_white";
  };

  const [words, setWords] = useState<SubtitleWord[]>(initialTrack.words || []);
  const [stylePreset, setStylePreset] = useState<string>(
    getInitialPreset(initialTrack.style)
  );
  const [reframeMode, setReframeMode] = useState("blur");
  const [previewTime, setPreviewTime] = useState(1.0);
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string | null>(null);

  const [isSaving, setIsSaving] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isRerendering, setIsRerendering] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (initialTrack) {
      setWords(initialTrack.words || []);
      setStylePreset(getInitialPreset(initialTrack.style));
    }
  }, [initialTrack]);

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
      try {
        await saveFinishedClip(clipId);
      } catch {
        // finished clip sync fallback
      }
      setSaveSuccess(true);
      if (onClipUpdated) onClipUpdated();
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      alert(`Gagal menyimpan subtitle: ${err?.message || err}`);
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
        "Re-render video final dengan konfigurasi & subtitle ini sekarang?"
      )
    ) {
      return;
    }
    setIsRerendering(true);
    try {
      await updateClipSubtitles(clipId, words, stylePreset);
      await rerenderClip(clipId);
      try {
        await saveFinishedClip(clipId);
      } catch {}
      alert("Re-render berhasil! Video telah diperbarui.");
      if (onClipUpdated) onClipUpdated();
    } catch (err: any) {
      alert(`Gagal re-render: ${err?.message || err}`);
    } finally {
      setIsRerendering(false);
    }
  };

  return (
    <div className="marked-frame border border-line bg-surface p-6 shadow-2xl flex flex-col gap-6">
      <i className="crop-mark crop-tl" />
      <i className="crop-mark crop-tr" />
      <i className="crop-mark crop-bl" />
      <i className="crop-mark crop-br" />

      {/* Header */}
      <div className="flex items-center justify-between border-b border-line pb-3">
        <div className="flex items-center gap-2">
          <FileEdit className="w-4 h-4 text-action" />
          <h3 className="font-extrabold text-copy text-base uppercase tracking-wider">
            STUDIO EDITOR SUBTITLE & PRESET LIBASS
          </h3>
        </div>
        <span className="text-xs px-2.5 py-0.5 border border-line bg-card font-mono text-muted">
          REVISI #{initialTrack.revision}
        </span>
      </div>

      {/* Settings Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs font-mono">
        <div>
          <label className="block uppercase tracking-wider text-muted mb-1.5 flex items-center gap-1.5 font-bold">
            <Palette className="w-3.5 h-3.5 text-action" />
            Preset Style ASS
          </label>
          <select
            value={stylePreset}
            onChange={(e) => setStylePreset(e.target.value)}
            className="w-full px-3 py-2 bg-card border border-line text-copy text-xs focus:outline-none focus:border-action"
          >
            <option value="classic_white">Classic White</option>
            <option value="hormozi_bold">Hormozi Bold (Kuning)</option>
            <option value="fire_orange">Fire Orange</option>
            <option value="mrbeast_box">MrBeast Box</option>
            <option value="neon_glow">Neon Glow (Cyan)</option>
            <option value="minimal_clean">Minimal Clean</option>
            <option value="none">Tanpa Subtitle (No Subtitle)</option>
          </select>
        </div>

        <div>
          <label className="block uppercase tracking-wider text-muted mb-1.5 font-bold">
            Mode Reframe
          </label>
          <select
            value={reframeMode}
            onChange={(e) => setReframeMode(e.target.value)}
            className="w-full px-3 py-2 bg-card border border-line text-copy text-xs focus:outline-none focus:border-action"
          >
            <option value="blur">Blur Pillarbox (Lanczos)</option>
            <option value="center">Center Crop</option>
            <option value="stacked">Stacked Cam/Game</option>
          </select>
        </div>

        <div>
          <label className="block uppercase tracking-wider text-muted mb-1.5 font-bold">
            Waktu Preview (detik)
          </label>
          <input
            type="number"
            step="0.5"
            min="0"
            value={previewTime}
            onChange={(e) => setPreviewTime(parseFloat(e.target.value) || 0)}
            className="w-full px-3 py-2 bg-card border border-line text-copy text-xs font-mono focus:border-action focus:outline-none"
          />
        </div>
      </div>

      {/* Main Content: Word List + WYSIWYG Frame Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Word Grid */}
        <div className="flex flex-col gap-2">
          <div className="flex justify-between items-center text-xs text-muted font-mono">
            <span>DAFTAR KATA ASR ({words.length} kata)</span>
            <span>Edit teks per kata</span>
          </div>

          <div className="h-96 overflow-y-auto bg-card p-3 border border-line flex flex-col gap-2 pr-1 font-mono">
            {words.length === 0 ? (
              <div className="text-muted text-xs text-center py-16">
                Tidak ada transkrip kata untuk klip ini (gameplay highlight tanpa audio bicara).
              </div>
            ) : (
              words.map((w, idx) => (
                <div
                  key={idx}
                  className="flex items-center gap-2 p-2 bg-surface border border-line text-xs"
                >
                  <span className="font-mono text-[10px] text-muted w-20 shrink-0">
                    {w.start_s.toFixed(2)}s - {w.end_s.toFixed(2)}s
                  </span>
                  <input
                    type="text"
                    value={w.text}
                    onChange={(e) => handleWordChange(idx, e.target.value)}
                    className="flex-1 px-2.5 py-1 bg-card border border-line text-copy text-xs font-semibold focus:outline-none focus:border-action"
                  />
                </div>
              ))
            )}
          </div>
        </div>

        {/* WYSIWYG Frame Preview */}
        <div className="flex flex-col gap-2">
          <div className="flex justify-between items-center text-xs text-muted font-mono">
            <span>WYSIWYG LIBASS PREVIEW FRAME</span>
            <button
              onClick={handlePreviewFrame}
              disabled={isPreviewing}
              className="btn-ghost flex items-center gap-1.5 px-3 py-1 text-xs font-bold text-copy"
            >
              {isPreviewing ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Eye className="w-3.5 h-3.5 text-action" />
              )}
              <span>RENDER FRAME ({previewTime.toFixed(1)}s)</span>
            </button>
          </div>

          <div className="h-96 bg-card border border-line flex items-center justify-center overflow-hidden relative">
            {previewBlobUrl ? (
              <img
                src={previewBlobUrl}
                alt="WYSIWYG Preview"
                className="h-full w-auto object-contain"
              />
            ) : (
              <div className="flex flex-col items-center gap-2 text-muted text-xs p-6 text-center">
                <Sparkles className="w-8 h-8 text-action opacity-60" />
                <span>
                  Klik &ldquo;RENDER FRAME&rdquo; untuk melihat pratinjau visual
                  subtitles dengan font OFL dan efek warna asli.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Bottom Action Buttons */}
      <div className="flex items-center justify-between border-t border-line pt-4">
        <div className="flex items-center gap-3">
          <button
            onClick={handleSaveSubtitles}
            disabled={isSaving}
            className="btn-action flex items-center gap-2 px-5 py-2.5 text-xs font-bold text-bg"
          >
            {isSaving ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : saveSuccess ? (
              <Check className="w-4 h-4" />
            ) : null}
            <span>{saveSuccess ? "TERSIMPAN!" : "SIMPAN REVISI SUBTITLE"}</span>
          </button>

          <button
            onClick={handleRerender}
            disabled={isRerendering}
            className="btn-ghost flex items-center gap-2 px-5 py-2.5 text-xs font-bold text-copy"
          >
            {isRerendering ? (
              <Loader2 className="w-4 h-4 animate-spin text-action" />
            ) : (
              <RefreshCw className="w-4 h-4 text-action" />
            )}
            <span>RE-RENDER VIDEO FINAL</span>
          </button>
        </div>
      </div>
    </div>
  );
};
