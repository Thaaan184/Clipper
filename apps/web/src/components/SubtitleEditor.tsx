import React, { useEffect, useRef, useState } from "react";
import { SubtitleTrack, SubtitleWord } from "../types";
import {
  previewSubtitleFrame,
  rerenderClip,
  saveFinishedClip,
  updateClipSubtitles,
} from "../api";
import {
  AlertTriangle,
  ArrowUpDown,
  Check,
  ChevronDown,
  ChevronUp,
  Eye,
  FileEdit,
  GripVertical,
  Loader2,
  Palette,
  Plus,
  RefreshCw,
  RotateCcw,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";

interface SubtitleEditorProps {
  clipId: string;
  initialTrack: SubtitleTrack;
  onClipUpdated?: () => void;
}

export const SPEAKER_CONFIGS = [
  { id: "speaker_1", label: "Speaker 1", color: "#FFFFFF", name: "Default (Putih)" },
  { id: "speaker_2", label: "Speaker 2", color: "#FF8C00", name: "Fire Orange" },
  { id: "speaker_3", label: "Speaker 3", color: "#00FFFF", name: "Neon Cyan" },
  { id: "speaker_4", label: "Speaker 4", color: "#00FF7F", name: "Spring Green" },
  { id: "speaker_5", label: "Speaker 5", color: "#FF00B4", name: "Magenta" },
];

function getSpeakerColor(spkId?: string): string {
  const found = SPEAKER_CONFIGS.find((s) => s.id === spkId);
  return found ? found.color : "#FFFFFF";
}

function getSpeakerLabel(spkId?: string): string {
  const found = SPEAKER_CONFIGS.find((s) => s.id === spkId);
  return found ? found.label : "Speaker 1";
}

function formatSec(s: number): string {
  if (isNaN(s)) return "0.00";
  return s.toFixed(2);
}

function parseSecInput(val: string, fallback: number): number {
  val = val.trim();
  if (!val) return fallback;
  if (val.includes(":")) {
    const parts = val.split(":");
    if (parts.length === 2) {
      const m = parseFloat(parts[0]);
      const s = parseFloat(parts[1]);
      if (!isNaN(m) && !isNaN(s)) return Math.max(0, m * 60 + s);
    } else if (parts.length === 3) {
      const h = parseFloat(parts[0]);
      const m = parseFloat(parts[1]);
      const s = parseFloat(parts[2]);
      if (!isNaN(h) && !isNaN(m) && !isNaN(s)) return Math.max(0, h * 3600 + m * 60 + s);
    }
  }
  const num = parseFloat(val);
  return isNaN(num) ? fallback : Math.max(0, num);
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

  const getInitialPosition = (track: SubtitleTrack): "bottom" | "top" => {
    if (track.subtitle_position === "top" || track.subtitle_position === "bottom") {
      return track.subtitle_position;
    }
    if (track.style && typeof track.style === "object" && (track.style as any).subtitle_position) {
      return (track.style as any).subtitle_position === "top" ? "top" : "bottom";
    }
    return "bottom";
  };

  const [words, setWords] = useState<SubtitleWord[]>(initialTrack.words || []);
  const [stylePreset, setStylePreset] = useState<string>(
    getInitialPreset(initialTrack.style)
  );
  const [subtitlePosition, setSubtitlePosition] = useState<"bottom" | "top">(
    getInitialPosition(initialTrack)
  );
  const [dragScope, setDragScope] = useState<"speaker" | "all" | "single">("speaker");
  const [reframeMode, setReframeMode] = useState("blur");
  const [previewTime, setPreviewTime] = useState(1.0);
  const [previewBlobUrl, setPreviewBlobUrl] = useState<string | null>(null);

  const [selectedWordIdx, setSelectedWordIdx] = useState<number | null>(0);

  const [isSaving, setIsSaving] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // List drag-and-drop reorder state
  const [draggedRowIndex, setDraggedRowIndex] = useState<number | null>(null);
  const [dragOverRowIndex, setDragOverRowIndex] = useState<number | null>(null);

  // In-App Re-render Modal state
  const [rerenderModal, setRerenderModal] = useState<{
    isOpen: boolean;
    status: "confirm" | "rendering" | "success" | "error";
    progress: number;
    message: string;
    error?: string;
  }>({
    isOpen: false,
    status: "confirm",
    progress: 0,
    message: "",
  });

  // Dragging state inside WYSIWYG preview frame (vertical canvas positioning)
  const previewFrameRef = useRef<HTMLDivElement | null>(null);
  const [draggingWordIdx, setDraggingWordIdx] = useState<number | null>(null);
  const [dragStartY, setDragStartY] = useState<number>(0);
  const [dragStartPosY, setDragStartPosY] = useState<number>(1680);
  const dragInitialPositionsRef = useRef<Map<number, number>>(new Map());

  useEffect(() => {
    if (initialTrack) {
      setWords(initialTrack.words || []);
      setStylePreset(getInitialPreset(initialTrack.style));
      setSubtitlePosition(getInitialPosition(initialTrack));
      if ((initialTrack.words || []).length > 0) {
        setSelectedWordIdx(0);
        setPreviewTime(initialTrack.words[0].start_s);
      }
    }
  }, [initialTrack]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  // List Reorder: Drag and Drop Handlers
  const handleListDragStart = (idx: number, e: React.DragEvent) => {
    setDraggedRowIndex(idx);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", idx.toString());
  };

  const handleListDragOver = (idx: number, e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (dragOverRowIndex !== idx) {
      setDragOverRowIndex(idx);
    }
  };

  const handleListDrop = (targetIdx: number, e: React.DragEvent) => {
    e.preventDefault();
    if (draggedRowIndex === null || draggedRowIndex === targetIdx) {
      setDraggedRowIndex(null);
      setDragOverRowIndex(null);
      return;
    }

    setWords((prev) => {
      const next = [...prev];
      const [moved] = next.splice(draggedRowIndex, 1);
      next.splice(targetIdx, 0, moved);
      return next.map((item, i) => ({ ...item, idx: i }));
    });

    setSelectedWordIdx(targetIdx);
    setDraggedRowIndex(null);
    setDragOverRowIndex(null);
    showToast(`Urutan subtitle #${draggedRowIndex + 1} dipindah ke #${targetIdx + 1}`);
  };

  const handleListDragEnd = () => {
    setDraggedRowIndex(null);
    setDragOverRowIndex(null);
  };

  // Move up/down single step
  const handleMoveRow = (idx: number, direction: "up" | "down", e: React.MouseEvent) => {
    e.stopPropagation();
    const targetIdx = direction === "up" ? idx - 1 : idx + 1;
    if (targetIdx < 0 || targetIdx >= words.length) return;

    setWords((prev) => {
      const next = [...prev];
      const [moved] = next.splice(idx, 1);
      next.splice(targetIdx, 0, moved);
      return next.map((item, i) => ({ ...item, idx: i }));
    });
    setSelectedWordIdx(targetIdx);
  };

  // Sort by start_s ascending
  const handleSortByTime = () => {
    setWords((prev) => {
      const sorted = [...prev].sort(
        (a, b) => a.start_s - b.start_s || a.end_s - b.end_s
      );
      return sorted.map((w, i) => ({ ...w, idx: i }));
    });
    showToast("Daftar subtitle diurutkan berdasarkan timestamp.");
  };

  const handleWordTextChange = (idx: number, newText: string) => {
    setWords((prev) =>
      prev.map((w, i) => (i === idx ? { ...w, text: newText } : w))
    );
  };

  const handleWordSpeakerChange = (idx: number, newSpeaker: string) => {
    setWords((prev) =>
      prev.map((w, i) => (i === idx ? { ...w, speaker: newSpeaker } : w))
    );
  };

  const handleWordStartChange = (idx: number, rawVal: string) => {
    setWords((prev) =>
      prev.map((w, i) => {
        if (i !== idx) return w;
        const newStart = parseSecInput(rawVal, w.start_s);
        return { ...w, start_s: newStart };
      })
    );
  };

  const handleWordEndChange = (idx: number, rawVal: string) => {
    setWords((prev) =>
      prev.map((w, i) => {
        if (i !== idx) return w;
        const newEnd = parseSecInput(rawVal, w.end_s);
        return { ...w, end_s: newEnd };
      })
    );
  };

  const handleResetWordPosY = (idx: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setWords((prev) =>
      prev.map((w, i) => (i === idx ? { ...w, pos_y: null } : w))
    );
    showToast("Posisi visual dikembalikan ke Auto (Stack)");
  };

  const handleAddWord = () => {
    setWords((prev) => {
      const last = prev[prev.length - 1];
      const start = last ? Math.round((last.end_s + 0.1) * 100) / 100 : 0.0;
      const end = Math.round((start + 2.0) * 100) / 100;
      const newWord: SubtitleWord = {
        idx: prev.length,
        start_s: start,
        end_s: end,
        text: "Subtitle baru",
        speaker: "speaker_1",
        pos_y: null,
      };
      return [...prev, newWord];
    });
    setSelectedWordIdx(words.length);
  };

  const handleDeleteWord = (idx: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setWords((prev) =>
      prev.filter((_, i) => i !== idx).map((w, i) => ({ ...w, idx: i }))
    );
    if (selectedWordIdx === idx) {
      setSelectedWordIdx(null);
    }
  };

  const handleApplyPresetLocation = (targetPos: "bottom" | "top") => {
    setSubtitlePosition(targetPos);
    const targetBaseY = targetPos === "top" ? 420 : 1680;
    setWords((prev) =>
      prev.map((w) => ({
        ...w,
        pos_y: targetBaseY,
      }))
    );
    showToast(
      targetPos === "top"
        ? "Semua subtitle dipindahkan ke preset ATAS (Y=420 - Bebas Caption YouTube Shorts)"
        : "Semua subtitle dipindahkan ke preset BAWAH (Y=1680 - Standar)"
    );
  };

  const handleApplySpeakerPresetLocation = (
    speaker: string,
    targetPos: "bottom" | "top"
  ) => {
    const targetBaseY = targetPos === "top" ? 420 : 1680;
    setWords((prev) =>
      prev.map((w) =>
        (w.speaker || "speaker_1") === speaker ? { ...w, pos_y: targetBaseY } : w
      )
    );
    showToast(
      `Semua subtitle ${getSpeakerLabel(speaker)} dipindahkan ke ${
        targetPos === "top" ? "ATAS (Y=420)" : "BAWAH (Y=1680)"
      }`
    );
  };

  const handleSaveSubtitles = async () => {
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      await updateClipSubtitles(clipId, words, stylePreset, subtitlePosition);
      try {
        await saveFinishedClip(clipId);
      } catch {
        // finished clip sync fallback
      }
      setSaveSuccess(true);
      showToast("Revisi subtitle & posisi berhasil disimpan!");
      if (onClipUpdated) onClipUpdated();
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      showToast(`Gagal menyimpan subtitle: ${err?.message || err}`);
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
        words,
        subtitlePosition
      );
      if (previewBlobUrl) {
        URL.revokeObjectURL(previewBlobUrl);
      }
      const url = URL.createObjectURL(blob);
      setPreviewBlobUrl(url);
    } catch (err: any) {
      showToast(`Gagal render frame preview: ${err?.message || err}`);
    } finally {
      setIsPreviewing(false);
    }
  };

  // Re-render execution with in-app compact progress popup
  const handleOpenRerenderModal = () => {
    setRerenderModal({
      isOpen: true,
      status: "confirm",
      progress: 0,
      message: "Re-render video final 1080x1920 dengan revisi subtitle & urutan ini?",
    });
  };

  const handleStartRerender = async () => {
    setRerenderModal({
      isOpen: true,
      status: "rendering",
      progress: 15,
      message: "Menyimpan revisi subtitle & urutan...",
    });

    try {
      await updateClipSubtitles(clipId, words, stylePreset, subtitlePosition);

      setRerenderModal((prev) => ({
        ...prev,
        progress: 40,
        message: "Memproses filtergraph FFmpeg & burning libass...",
      }));

      // Simulate step progress while server renders
      const progTimer = setInterval(() => {
        setRerenderModal((prev) => {
          if (prev.status !== "rendering") return prev;
          const nextProg = Math.min(88, prev.progress + 12);
          return {
            ...prev,
            progress: nextProg,
            message:
              nextProg > 70
                ? "Mengompresi video final 1080x1920..."
                : "Memproses filtergraph FFmpeg & burning libass...",
          };
        });
      }, 700);

      await rerenderClip(clipId, {
        reframe_mode: reframeMode,
        subtitle_style: stylePreset,
        subtitle_position: subtitlePosition,
      });

      clearInterval(progTimer);

      try {
        await saveFinishedClip(clipId);
      } catch {}

      setRerenderModal({
        isOpen: true,
        status: "success",
        progress: 100,
        message: "Re-render berhasil! Video final telah diperbarui.",
      });

      if (onClipUpdated) onClipUpdated();

      setTimeout(() => {
        setRerenderModal((prev) => ({ ...prev, isOpen: false }));
      }, 1500);
    } catch (err: any) {
      setRerenderModal({
        isOpen: true,
        status: "error",
        progress: 0,
        message: "Gagal memproses re-render video.",
        error: String(err?.message || err),
      });
    }
  };

  // Calculate active subtitles at previewTime
  const activeSubtitles = words.filter(
    (w) => w.start_s <= previewTime && previewTime <= w.end_s
  );

  // If no subtitles active at current time, fallback to selected subtitle if present
  const displayedSubtitles =
    activeSubtitles.length > 0
      ? activeSubtitles
      : selectedWordIdx !== null && words[selectedWordIdx]
      ? [words[selectedWordIdx]]
      : [];

  // Drag handlers in WYSIWYG preview frame (vertical canvas positioning)
  const handleCanvasDragStart = (
    wIdx: number,
    currentAssPosY: number,
    clientY: number
  ) => {
    setDraggingWordIdx(wIdx);
    setDragStartY(clientY);
    setDragStartPosY(currentAssPosY);

    const defaultBaseY = subtitlePosition === "top" ? 420 : 1680;
    const posMap = new Map<number, number>();
    words.forEach((w, idx) => {
      const y =
        w.pos_y !== null && w.pos_y !== undefined ? w.pos_y : defaultBaseY;
      posMap.set(idx, y);
    });
    dragInitialPositionsRef.current = posMap;
  };

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (draggingWordIdx === null || !previewFrameRef.current) return;
      const rect = previewFrameRef.current.getBoundingClientRect();
      const frameHeightPx = rect.height || 480;
      const deltaClientY = e.clientY - dragStartY;
      const deltaAssY = deltaClientY * (1920 / frameHeightPx);

      const targetWord = words[draggingWordIdx];
      const targetSpeaker = targetWord?.speaker || "speaker_1";
      const initMap = dragInitialPositionsRef.current;
      const defaultBaseY = subtitlePosition === "top" ? 420 : 1680;

      setWords((prev) =>
        prev.map((w, idx) => {
          let shouldMove = false;
          if (dragScope === "single") {
            shouldMove = idx === draggingWordIdx;
          } else if (dragScope === "all") {
            shouldMove = true;
          } else if (dragScope === "speaker") {
            shouldMove = (w.speaker || "speaker_1") === targetSpeaker;
          }

          if (!shouldMove) return w;

          const baseInitialY = initMap.get(idx) ?? defaultBaseY;
          const newPosY = Math.round(
            Math.min(1820, Math.max(180, baseInitialY + deltaAssY))
          );
          return { ...w, pos_y: newPosY };
        })
      );
    };

    const handleMouseUp = () => {
      if (draggingWordIdx !== null) {
        const targetWord = words[draggingWordIdx];
        const spk = targetWord?.speaker || "speaker_1";
        if (dragScope === "speaker") {
          showToast(
            `Posisi visual seluruh baris ${getSpeakerLabel(spk)} berhasil digeser bersamaan`
          );
        } else if (dragScope === "all") {
          showToast("Posisi visual seluruh subtitle berhasil digeser bersamaan");
        } else {
          showToast(`Posisi visual subtitle #${draggingWordIdx + 1} berhasil digeser`);
        }
        setDraggingWordIdx(null);
      }
    };

    if (draggingWordIdx !== null) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
    }

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [draggingWordIdx, dragStartY, dragStartPosY, dragScope, subtitlePosition, words]);

  return (
    <div className="marked-frame border border-line bg-surface p-6 shadow-2xl flex flex-col gap-6 relative">
      <i className="crop-mark crop-tl" />
      <i className="crop-mark crop-tr" />
      <i className="crop-mark crop-bl" />
      <i className="crop-mark crop-br" />

      {/* Toast Notification */}
      {toastMessage && (
        <div className="absolute top-4 right-6 z-40 bg-card border border-action/50 px-4 py-2 text-xs font-mono text-copy shadow-xl flex items-center gap-2">
          <span className="w-2 h-2 bg-action inline-block"></span>
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Compact Re-render Modal Overlay */}
      {rerenderModal.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="marked-frame border border-line bg-surface max-w-sm w-full p-5 shadow-2xl flex flex-col gap-4 font-mono text-xs">
            <i className="crop-mark crop-tl" />
            <i className="crop-mark crop-tr" />
            <i className="crop-mark crop-bl" />
            <i className="crop-mark crop-br" />

            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-line pb-2.5">
              <span className="font-extrabold uppercase text-copy tracking-wider flex items-center gap-2">
                {rerenderModal.status === "rendering" ? (
                  <RefreshCw className="w-4 h-4 text-action animate-spin" />
                ) : rerenderModal.status === "success" ? (
                  <Check className="w-4 h-4 text-emerald-400" />
                ) : rerenderModal.status === "error" ? (
                  <AlertTriangle className="w-4 h-4 text-err" />
                ) : (
                  <RefreshCw className="w-4 h-4 text-action" />
                )}
                <span>
                  {rerenderModal.status === "confirm"
                    ? "KONFIRMASI RE-RENDER"
                    : rerenderModal.status === "rendering"
                    ? "RE-RENDERING VIDEO..."
                    : rerenderModal.status === "success"
                    ? "RE-RENDER SELESAI"
                    : "RE-RENDER GAGAL"}
                </span>
              </span>
              {rerenderModal.status !== "rendering" && (
                <button
                  type="button"
                  onClick={() =>
                    setRerenderModal((prev) => ({ ...prev, isOpen: false }))
                  }
                  className="text-muted hover:text-copy"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>

            {/* Modal Body */}
            {rerenderModal.status === "confirm" && (
              <div className="flex flex-col gap-4">
                <p className="text-muted text-xs leading-relaxed">
                  {rerenderModal.message}
                </p>
                <div className="flex items-center justify-end gap-2 pt-2 border-t border-line">
                  <button
                    type="button"
                    onClick={() =>
                      setRerenderModal((prev) => ({ ...prev, isOpen: false }))
                    }
                    className="btn-ghost px-4 py-2 text-xs font-bold text-copy"
                  >
                    BATAL
                  </button>
                  <button
                    type="button"
                    onClick={handleStartRerender}
                    className="btn-action px-4 py-2 text-xs font-bold text-bg"
                  >
                    MULAI RE-RENDER
                  </button>
                </div>
              </div>
            )}

            {rerenderModal.status === "rendering" && (
              <div className="flex flex-col gap-3 py-1">
                <div className="flex items-center justify-between text-[11px] text-muted">
                  <span>{rerenderModal.message}</span>
                  <span className="text-action font-bold">
                    {rerenderModal.progress}%
                  </span>
                </div>
                {/* Progress Bar */}
                <div className="w-full bg-card h-2 border border-line overflow-hidden">
                  <div
                    className="bg-action h-full transition-all duration-300"
                    style={{ width: `${rerenderModal.progress}%` }}
                  />
                </div>
                <span className="text-[10px] text-muted text-center pt-1">
                  Harap tunggu, proses rendering berjalan di server...
                </span>
              </div>
            )}

            {rerenderModal.status === "success" && (
              <div className="flex flex-col items-center gap-2 py-3 text-center">
                <Check className="w-8 h-8 text-emerald-400 mb-1" />
                <span className="font-bold text-copy">{rerenderModal.message}</span>
                <span className="text-[10px] text-muted">
                  Menutup popup otomatis...
                </span>
              </div>
            )}

            {rerenderModal.status === "error" && (
              <div className="flex flex-col gap-3">
                <div className="p-3 bg-err/10 border border-err/30 text-err text-xs">
                  <p className="font-bold mb-1">{rerenderModal.message}</p>
                  <p className="font-mono text-[11px] opacity-90">
                    {rerenderModal.error}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    setRerenderModal((prev) => ({ ...prev, isOpen: false }))
                  }
                  className="btn-ghost w-full py-2 text-xs font-bold text-copy border border-line"
                >
                  TUTUP
                </button>
              </div>
            )}
          </div>
        </div>
      )}

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
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 text-xs font-mono">
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
            <option value="classic_white">Classic White (Putih)</option>
            <option value="fire_orange">Fire Orange (Oranye)</option>
            <option value="hormozi_bold">Hormozi Bold (Kuning/Hijau)</option>
            <option value="mrbeast_box">MrBeast Box (Bold Gold)</option>
            <option value="neon_glow">Neon Glow (Cyan/Magenta)</option>
            <option value="minimal_clean">Minimal Clean (Putih Minimalis)</option>
            <option value="none">Tanpa Subtitle (No Subtitle)</option>
          </select>
        </div>

        <div>
          <label className="block uppercase tracking-wider text-muted mb-1.5 font-bold">
            Preset Lokasi Awal
          </label>
          <select
            value={subtitlePosition}
            onChange={(e) => handleApplyPresetLocation(e.target.value as "bottom" | "top")}
            className="w-full px-3 py-2 bg-card border border-line text-copy text-xs focus:outline-none focus:border-action"
          >
            <option value="bottom">Bawah (Y=1680 - Standar)</option>
            <option value="top">Atas (Y=420 - Safe YT Shorts)</option>
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

      {/* Main Content: Word List with Drag Reordering + Visual WYSIWYG Frame Preview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Subtitle List */}
        <div className="flex flex-col gap-2">
          <div className="flex justify-between items-center text-xs text-muted font-mono">
            <span className="flex items-center gap-1.5">
              <span>DAFTAR SUBTITLE & TIMING ({words.length} baris)</span>
            </span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={handleSortByTime}
                className="flex items-center gap-1 text-[10px] text-muted hover:text-copy"
                title="Urutkan baris berdasarkan timestamp mulai secara otomatis"
              >
                <ArrowUpDown className="w-3 h-3" />
                <span>URUTKAN WAKTU</span>
              </button>
              <button
                type="button"
                onClick={handleAddWord}
                className="flex items-center gap-1 text-[11px] text-action hover:underline font-bold"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>TAMBAH BARIS</span>
              </button>
            </div>
          </div>

          {/* Note Banner */}
          <div className="bg-card/90 border border-line px-3 py-1.5 text-[11px] font-mono text-muted flex items-start sm:items-center gap-2">
            <span className="text-action font-extrabold uppercase shrink-0">CATATAN:</span>
            <span className="leading-tight">
              Hit box geser urutan khusus di icon <strong className="text-copy">Grip (⋮⋮ #{'N'})</strong> paling kiri. Kolom teks dan timing bebas diketik, diklik, dan diblok tanpa bisa tergeser.
            </span>
          </div>

          <div className="h-[480px] overflow-y-auto bg-card p-2.5 border border-line flex flex-col gap-2 font-mono">
            {words.length === 0 ? (
              <div className="text-muted text-xs text-center py-20 flex flex-col items-center gap-3">
                <span>Tidak ada subtitle untuk klip ini.</span>
                <button
                  type="button"
                  onClick={handleAddWord}
                  className="btn-action px-3 py-1 text-xs font-bold text-bg"
                >
                  + Tambah Subtitle Manual
                </button>
              </div>
            ) : (
              words.map((w, idx) => {
                const isSelected = selectedWordIdx === idx;
                const spkColor = getSpeakerColor(w.speaker);
                const isDragOver = dragOverRowIndex === idx;
                const isDragged = draggedRowIndex === idx;

                return (
                  <div
                    key={idx}
                    onDragOver={(e) => handleListDragOver(idx, e)}
                    onDragEnd={handleListDragEnd}
                    onDrop={(e) => handleListDrop(idx, e)}
                    onClick={() => {
                      setSelectedWordIdx(idx);
                      setPreviewTime(w.start_s);
                    }}
                    className={`flex flex-col gap-2 p-2.5 bg-surface border transition-all text-xs ${
                      isSelected
                        ? "border-action shadow-md bg-surface/90 ring-1 ring-action/50"
                        : "border-line hover:border-zinc-700"
                    } ${isDragOver ? "border-t-2 border-t-action bg-action/5" : ""} ${
                      isDragged ? "opacity-30 scale-[0.99]" : ""
                    }`}
                  >
                    {/* Top Row: Drag Handle + #ID + Speaker selector + Timing IN/OUT + Pos Y */}
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        {/* Dedicated Drag Hitbox (Grip Handle & Row Number ONLY) */}
                        <div
                          draggable={true}
                          onDragStart={(e) => {
                            e.stopPropagation();
                            handleListDragStart(idx, e);
                          }}
                          onDragEnd={handleListDragEnd}
                          className="flex items-center gap-1 cursor-grab active:cursor-grabbing text-action bg-card border border-action/30 hover:border-action px-1.5 py-0.5 select-none transition-colors"
                          title="Drag dari kotak ini untuk memindahkan urutan baris (misal geser #3 jadi #2)"
                        >
                          <GripVertical className="w-3.5 h-3.5 text-action" />
                          <span className="font-extrabold text-[11px] text-copy min-w-[20px]">
                            #{idx + 1}
                          </span>
                        </div>

                        {/* Quick Up/Down buttons */}
                        <div className="flex items-center gap-0.5 mr-1">
                          <button
                            type="button"
                            disabled={idx === 0}
                            onClick={(e) => handleMoveRow(idx, "up", e)}
                            className="p-0.5 text-muted hover:text-action disabled:opacity-20"
                            title="Geser baris naik"
                          >
                            <ChevronUp className="w-3 h-3" />
                          </button>
                          <button
                            type="button"
                            disabled={idx === words.length - 1}
                            onClick={(e) => handleMoveRow(idx, "down", e)}
                            className="p-0.5 text-muted hover:text-action disabled:opacity-20"
                            title="Geser baris turun"
                          >
                            <ChevronDown className="w-3 h-3" />
                          </button>
                        </div>

                        {/* Speaker Badge / Dropdown */}
                        <select
                          value={w.speaker || "speaker_1"}
                          onChange={(e) => handleWordSpeakerChange(idx, e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          onMouseDown={(e) => e.stopPropagation()}
                          style={{ borderColor: spkColor, color: spkColor }}
                          className="px-2 py-0.5 bg-card border font-bold text-[10px] focus:outline-none"
                        >
                          {SPEAKER_CONFIGS.map((spk) => (
                            <option
                              key={spk.id}
                              value={spk.id}
                              className="bg-card text-copy"
                            >
                              {spk.label} ({spk.name})
                            </option>
                          ))}
                        </select>
                      </div>

                      {/* Timestamps */}
                      <div className="flex items-center gap-1 font-mono text-[11px]">
                        <span className="text-[10px] text-muted">IN:</span>
                        <input
                          type="text"
                          defaultValue={formatSec(w.start_s)}
                          key={`st-${idx}-${w.start_s}`}
                          draggable={false}
                          onMouseDown={(e) => e.stopPropagation()}
                          onDragStart={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                          }}
                          onClick={(e) => e.stopPropagation()}
                          onBlur={(e) => handleWordStartChange(idx, e.target.value)}
                          className="w-13 px-1.5 py-0.5 bg-card border border-line text-copy text-[11px] text-center focus:border-action focus:outline-none cursor-text select-text"
                          title="Waktu mulai (detik atau MM:SS)"
                        />
                        <span className="text-muted text-[10px]">→</span>
                        <span className="text-[10px] text-muted">OUT:</span>
                        <input
                          type="text"
                          defaultValue={formatSec(w.end_s)}
                          key={`en-${idx}-${w.end_s}`}
                          draggable={false}
                          onMouseDown={(e) => e.stopPropagation()}
                          onDragStart={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                          }}
                          onClick={(e) => e.stopPropagation()}
                          onBlur={(e) => handleWordEndChange(idx, e.target.value)}
                          className="w-13 px-1.5 py-0.5 bg-card border border-line text-copy text-[11px] text-center focus:border-action focus:outline-none cursor-text select-text"
                          title="Waktu selesai (detik atau MM:SS)"
                        />
                        <span className="text-[10px] text-action font-mono bg-action/10 px-1 py-0.5 border border-action/20">
                          {Math.max(0, w.end_s - w.start_s).toFixed(2)}s
                        </span>
                      </div>

                      {/* Pos Y Indicator + Reset */}
                      <div className="flex items-center gap-1">
                        <span
                          className={`text-[10px] px-1.5 py-0.5 border ${
                            w.pos_y !== null && w.pos_y !== undefined
                              ? "border-action text-action bg-action/10"
                              : "border-line text-muted bg-card"
                          }`}
                          title="Koordinat vertikal ASS (bisa di-drag di preview)"
                        >
                          Y: {w.pos_y !== null && w.pos_y !== undefined ? `${w.pos_y}px` : "Auto"}
                        </span>
                        {w.pos_y !== null && w.pos_y !== undefined && (
                          <button
                            type="button"
                            onClick={(e) => handleResetWordPosY(idx, e)}
                            title="Kembalikan posisi ke Auto Stack"
                            className="p-0.5 text-muted hover:text-copy"
                          >
                            <RotateCcw className="w-3 h-3" />
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={(e) => handleDeleteWord(idx, e)}
                          title="Hapus baris subtitle ini"
                          className="p-1 text-muted hover:text-err transition-colors shrink-0 ml-1"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Bottom Row: Text input (Aman diblok & diedit tanpa tergeser) */}
                    <input
                      type="text"
                      value={w.text}
                      draggable={false}
                      onMouseDown={(e) => e.stopPropagation()}
                      onDragStart={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                      }}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => handleWordTextChange(idx, e.target.value)}
                      className="w-full px-2.5 py-1.5 bg-card border border-line text-copy text-xs font-semibold focus:outline-none focus:border-action cursor-text select-text"
                      placeholder="Teks subtitle..."
                    />
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Visual WYSIWYG Frame Preview with Interactive Vertical Dragging */}
        <div className="flex flex-col gap-2">
          <div className="flex justify-between items-center text-xs text-muted font-mono">
            <span>WYSIWYG 9:16 PREVIEW & DRAG POSISI VISUAL</span>
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
              <span>RENDER SNAPSHOT ({previewTime.toFixed(1)}s)</span>
            </button>
          </div>

          {/* Drag Scope & Quick Preset Bar */}
          <div className="bg-card border border-line p-2 text-xs font-mono flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-1.5">
              <span className="text-muted font-bold text-[10px] uppercase">Target Drag:</span>
              <select
                value={dragScope}
                onChange={(e) => setDragScope(e.target.value as "speaker" | "all" | "single")}
                className="bg-bg border border-line px-2 py-0.5 text-copy text-[11px] font-semibold focus:border-action focus:outline-none"
              >
                <option value="speaker">Speaker Terpilih (Batch semua kata speaker ini)</option>
                <option value="all">Semua Subtitle (Batch geser seluruh klip)</option>
                <option value="single">Hanya Teks Ini (Spesifik 1 baris)</option>
              </select>
            </div>
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => handleApplyPresetLocation("top")}
                className={`px-2 py-0.5 text-[10px] font-bold border transition-colors ${
                  subtitlePosition === "top"
                    ? "bg-action text-bg border-action"
                    : "bg-surface border-line text-muted hover:text-copy"
                }`}
                title="Pindahkan seluruh subtitle ke ATAS (Y=420) agar bebas caption YouTube Shorts"
              >
                ↑ ATAS (SHORTS)
              </button>
              <button
                type="button"
                onClick={() => handleApplyPresetLocation("bottom")}
                className={`px-2 py-0.5 text-[10px] font-bold border transition-colors ${
                  subtitlePosition === "bottom"
                    ? "bg-action text-bg border-action"
                    : "bg-surface border-line text-muted hover:text-copy"
                }`}
                title="Pindahkan seluruh subtitle ke BAWAH (Y=1680 - Standar)"
              >
                ↓ BAWAH (STANDAR)
              </button>
              {selectedWordIdx !== null && words[selectedWordIdx] && (
                <button
                  type="button"
                  onClick={() =>
                    handleApplySpeakerPresetLocation(
                      words[selectedWordIdx]?.speaker || "speaker_1",
                      subtitlePosition === "top" ? "bottom" : "top"
                    )
                  }
                  className="px-2 py-0.5 text-[10px] font-bold border border-action/40 bg-action/10 text-action hover:bg-action/20"
                  title="Pindahkan hanya speaker yang aktif saat ini"
                >
                  ⚡ SPK #{getSpeakerLabel(words[selectedWordIdx]?.speaker).replace("Speaker ", "")} {subtitlePosition === "top" ? "↓ BAWAH" : "↑ ATAS"}
                </button>
              )}
            </div>
          </div>

          <div className="h-[480px] bg-card border border-line flex items-center justify-center p-3 relative overflow-hidden select-none">
            {/* 9:16 Frame Container */}
            <div
              ref={previewFrameRef}
              className="relative aspect-[9/16] h-full max-h-full bg-zinc-950 border border-line shadow-2xl flex items-center justify-center overflow-hidden"
              style={{ width: "270px" }}
            >
              {/* Snapshot Background if present */}
              {previewBlobUrl ? (
                <img
                  src={previewBlobUrl}
                  alt="WYSIWYG Preview"
                  className="absolute inset-0 w-full h-full object-cover pointer-events-none"
                />
              ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-muted text-[11px] p-4 text-center pointer-events-none opacity-40">
                  <Sparkles className="w-6 h-6 text-action" />
                  <span>Frame 9:16 (1080x1920)</span>
                </div>
              )}

              {/* Center guideline */}
              <div className="absolute inset-x-0 top-1/2 border-t border-dashed border-white/10 pointer-events-none" />

              {/* Subtitles Overlay: Multiple concurrent subtitles appear simultaneously */}
              {displayedSubtitles.map((sub, sIdx) => {
                const defaultAssY = 1680 - sIdx * 140;
                const activeAssY =
                  sub.pos_y !== null && sub.pos_y !== undefined
                    ? sub.pos_y
                    : defaultAssY;
                const topPercent = (activeAssY / 1920) * 100;
                const spkColor = getSpeakerColor(sub.speaker);
                const isSelected = selectedWordIdx === sub.idx;
                const isDragging = draggingWordIdx === sub.idx;

                return (
                  <div
                    key={sub.idx}
                    onMouseDown={(e) => {
                      e.stopPropagation();
                      setSelectedWordIdx(sub.idx);
                      handleCanvasDragStart(sub.idx, activeAssY, e.clientY);
                    }}
                    style={{
                      top: `${topPercent}%`,
                      transform: "translate(-50%, -100%)",
                      borderColor: spkColor,
                    }}
                    className={`absolute left-1/2 w-[88%] bg-black/85 border-2 px-2.5 py-1.5 shadow-2xl cursor-grab active:cursor-grabbing transition-shadow z-20 ${
                      isSelected ? "ring-2 ring-action ring-offset-1 ring-offset-black" : ""
                    } ${isDragging ? "opacity-90 scale-[1.02]" : ""}`}
                  >
                    {/* Header bar of draggable card: Speaker name + Drag handle */}
                    <div className="flex items-center justify-between text-[9px] font-mono pb-0.5 border-b border-white/20 mb-1">
                      <span
                        className="font-extrabold uppercase px-1 py-0.2"
                        style={{ color: spkColor }}
                      >
                        {getSpeakerLabel(sub.speaker)}
                      </span>
                      <div className="flex items-center gap-1 text-muted">
                        <span>Y: {activeAssY}px</span>
                        <GripVertical className="w-3 h-3 text-action" />
                      </div>
                    </div>

                    {/* Subtitle text */}
                    <div
                      className="text-center font-bold text-xs leading-snug break-words"
                      style={{ color: spkColor }}
                    >
                      {sub.text || "(Teks kosong)"}
                    </div>

                    {/* Drag helper hint */}
                    {isSelected && (
                      <div className="absolute -bottom-5 left-1/2 -translate-x-1/2 bg-black/90 text-action text-[9px] font-mono px-1.5 py-0.5 border border-line whitespace-nowrap pointer-events-none">
                        GESER NAIK / TURUN
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Bottom status badge in preview */}
              <div className="absolute bottom-2 left-2 right-2 bg-black/80 border border-line px-2 py-1 text-[9px] font-mono text-muted flex items-center justify-between pointer-events-none">
                <span>T: {previewTime.toFixed(1)}s</span>
                <span>AKTIF: {displayedSubtitles.length} SUBTITLE</span>
              </div>
            </div>
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
            onClick={handleOpenRerenderModal}
            className="btn-ghost flex items-center gap-2 px-5 py-2.5 text-xs font-bold text-copy"
          >
            <RefreshCw className="w-4 h-4 text-action" />
            <span>RE-RENDER VIDEO FINAL</span>
          </button>
        </div>
      </div>
    </div>
  );
};
