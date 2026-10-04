import { useEffect, useState } from "react";
import {
  cancelJob,
  createJob,
  deleteJob,
  getCandidates,
  getClip,
  getClipSubtitles,
  getJob,
  getJobClips,
  getTimeline,
  listJobs,
  triggerRender,
  updateCandidate,
} from "./api";
import { CandidateCard } from "./components/CandidateCard";
import { ClipPlayer } from "./components/ClipPlayer";
import { EvaluationView } from "./components/EvaluationView";
import { JobForm } from "./components/JobForm";
import { ProgressTracker } from "./components/ProgressTracker";
import { SubtitleEditor } from "./components/SubtitleEditor";
import { TimelineVisualizer } from "./components/TimelineVisualizer";
import { Candidate, Clip, Job, JobParams, SubtitleTrack, TimelineData } from "./types";
import {
  ArrowRight,
  Award,
  Film,
  Layers,
  Palette,
  Play,
  RefreshCw,
  Sparkles,
  Trash2,
  Video,
} from "lucide-react";

export default function App(): JSX.Element {
  const [activeTab, setActiveTab] = useState<"home" | "proc" | "res" | "eval" | "spec">("home");

  const [currentJob, setCurrentJob] = useState<Job | null>(null);
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedCandId, setSelectedCandId] = useState<string | null>(null);
  const [renderedClips, setRenderedClips] = useState<Clip[]>([]);
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);

  const [activeClip, setActiveClip] = useState<Clip | null>(null);
  const [activeSubtitleTrack, setActiveSubtitleTrack] = useState<SubtitleTrack | null>(null);
  const [isEditingSubtitles, setIsEditingSubtitles] = useState(false);

  const [loading, setLoading] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Live 24fps timecode display
  const [timecode, setTimecode] = useState("00:00:00:00");

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 2500);
  };

  useEffect(() => {
    let frame = 0;
    const interval = setInterval(() => {
      frame++;
      const sec = Math.floor(frame / 24);
      const z = (n: number) => String(n).padStart(2, "0");
      const h = Math.floor(sec / 3600);
      const m = Math.floor((sec % 3600) / 60);
      const s = sec % 60;
      const f = frame % 24;
      setTimecode(`${z(h)}:${z(m)}:${z(s)}:${z(f)}`);
    }, 42);
    return () => clearInterval(interval);
  }, []);

  // Fetch recent jobs on load
  const loadRecentJobs = async () => {
    try {
      const list = await listJobs(6);
      setRecentJobs(list);
    } catch {
      // ignore
    }
  };

  useEffect(() => {
    loadRecentJobs();
  }, []);

  // Poll current job when active
  useEffect(() => {
    if (!currentJob) return;
    const isTerminal = ["done", "failed", "cancelled"].includes(currentJob.status);

    const fetchDetails = async (jobId: string) => {
      try {
        const updated = await getJob(jobId);
        setCurrentJob(updated);

        // Fetch candidates and timeline
        if (["awaiting_review", "rendering", "done"].includes(updated.status)) {
          const [tData, cData] = await Promise.all([
            getTimeline(updated.id).catch(() => null),
            getCandidates(updated.id).catch(() => ({ candidates: [] })),
          ]);
          if (tData) setTimeline(tData);
          if (cData) setCandidates(cData.candidates);
        }

        // Fetch clips if rendering or done
        if (["rendering", "done"].includes(updated.status)) {
          const clipsRes = await getJobClips(updated.id).catch(() => ({ clips: [] }));
          if (clipsRes && clipsRes.clips.length > 0) {
            setRenderedClips(clipsRes.clips);
            if (!activeClip) {
              setActiveClip(clipsRes.clips[0]);
            }
          }
        }
      } catch (err) {
        console.error("Failed to poll job:", err);
      }
    };

    // First fetch immediately
    fetchDetails(currentJob.id);

    if (isTerminal) return;

    const interval = setInterval(() => {
      fetchDetails(currentJob.id);
    }, 2500);

    return () => clearInterval(interval);
  }, [currentJob?.id, currentJob?.status]);

  const handleStartJob = async (
    url: string,
    genre: string,
    language: string,
    params: JobParams
  ) => {
    setLoading(true);
    try {
      const job = await createJob(url, genre, language, params);
      setCurrentJob(job);
      setTimeline(null);
      setCandidates([]);
      setSelectedCandId(null);
      setRenderedClips([]);
      setActiveClip(null);
      setActiveSubtitleTrack(null);
      setActiveTab("proc");
      showToast("Job pemrosesan sinyal berhasil dibuat!");
      loadRecentJobs();
    } catch (err) {
      showToast(`Gagal membuat job: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectRecentJob = async (job: Job) => {
    setCurrentJob(job);
    setActiveTab("proc");
    showToast(`Memuat data job ${job.id.slice(0, 8)}`);
    try {
      const [tData, cData, clipsRes] = await Promise.all([
        getTimeline(job.id).catch(() => null),
        getCandidates(job.id).catch(() => ({ candidates: [] })),
        getJobClips(job.id).catch(() => ({ clips: [] })),
      ]);
      if (tData) setTimeline(tData);
      if (cData) setCandidates(cData.candidates);
      if (clipsRes && clipsRes.clips.length > 0) {
        setRenderedClips(clipsRes.clips);
        setActiveClip(clipsRes.clips[0]);
      }
    } catch {
      // ignore
    }
  };

  const handleCancelJob = async () => {
    if (!currentJob) return;
    try {
      await cancelJob(currentJob.id);
      setCurrentJob({ ...currentJob, status: "cancelled" });
      showToast("Job berhasil dibatalkan.");
    } catch (err) {
      showToast(`Gagal membatalkan job: ${err}`);
    }
  };

  const handleDeleteJob = async (jobId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (!confirm(`Hapus proyek ${jobId.slice(0, 8)} secara permanen dari server?`)) {
      return;
    }
    try {
      await deleteJob(jobId);
      setRecentJobs((prev) => prev.filter((j) => j.id !== jobId));
      if (currentJob?.id === jobId) {
        setCurrentJob(null);
        setTimeline(null);
        setCandidates([]);
        setRenderedClips([]);
        setActiveClip(null);
        setActiveTab("home");
      }
      showToast("Proyek berhasil dihapus.");
    } catch (err: any) {
      showToast(`Gagal menghapus proyek: ${err.message || err}`);
    }
  };

  const handleUpdateStatus = async (
    candId: string,
    status: "kept" | "rejected"
  ) => {
    try {
      await updateCandidate(candId, { status });
      setCandidates((prev) =>
        prev.map((c) => (c.id === candId ? { ...c, status } : c))
      );
      showToast(`Kandidat ditandai ${status.toUpperCase()}`);
    } catch (err) {
      showToast(`Gagal update status kandidat: ${err}`);
    }
  };

  const handleUpdateTiming = async (
    candId: string,
    start_s: number,
    end_s: number
  ) => {
    try {
      await updateCandidate(candId, { user_start_s: start_s, user_end_s: end_s });
      setCandidates((prev) =>
        prev.map((c) =>
          c.id === candId ? { ...c, user_start_s: start_s, user_end_s: end_s } : c
        )
      );
      showToast("Timing boundary kandidat berhasil disimpan!");
    } catch (err) {
      showToast(`Gagal update timing kandidat: ${err}`);
    }
  };

  const handleTriggerRender = async () => {
    if (!currentJob) return;
    setIsRendering(true);
    try {
      await triggerRender(currentJob.id);
      setCurrentJob({
        ...currentJob,
        status: "rendering",
        progress: 0.80,
        error_code: null,
        error_message: null,
      });
      showToast("Batch render 9:16 dimulai untuk kandidat lolos kurasi!");
    } catch (err: any) {
      showToast(`Gagal trigger render: ${err.message || err}`);
    } finally {
      setIsRendering(false);
    }
  };

  const handleLoadClip = async (clipId: string) => {
    try {
      const clip = await getClip(clipId);
      setActiveClip(clip);
      const subs = await getClipSubtitles(clipId);
      setActiveSubtitleTrack(subs);
      setActiveTab("res");
      setIsEditingSubtitles(false);
      showToast(`Membuka klip ${clipId.slice(0, 8)}`);
    } catch (err) {
      showToast(`Gagal memuat klip: ${err}`);
    }
  };

  const keptCandidatesCount = candidates.filter((c) => c.status === "kept").length;

  return (
    <div className="min-h-screen bg-bg text-copy flex flex-col font-sans">
      {/* Cutting Room Header */}
      <header className="border-b border-line bg-surface/90 sticky top-0 z-50 px-6 py-3.5 flex items-center justify-between flex-wrap gap-4">
        {/* Brand */}
        <div
          className="flex items-center gap-3 cursor-pointer select-none"
          onClick={() => setActiveTab("home")}
        >
          <div className="w-3.5 h-3.5 bg-action" />
          <div className="flex items-baseline gap-2">
            <span className="font-extrabold text-base tracking-[0.16em] uppercase text-copy">
              CLIPFORGE
            </span>
            <span className="text-[10px] font-mono font-bold text-action">v2</span>
          </div>
        </div>

        {/* Cutting Room Navigation */}
        <nav className="flex items-center gap-1 sm:gap-2">
          <button
            onClick={() => setActiveTab("home")}
            className={`px-3 py-1.5 text-xs font-bold transition-all border-b-2 ${
              activeTab === "home"
                ? "border-action text-copy"
                : "border-transparent text-muted hover:text-copy"
            }`}
          >
            Home
          </button>
          <button
            onClick={() => setActiveTab("proc")}
            className={`px-3 py-1.5 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 ${
              activeTab === "proc"
                ? "border-action text-copy"
                : "border-transparent text-muted hover:text-copy"
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            <span>Processing & Review</span>
            {currentJob && (
              <span className="w-1.5 h-1.5 rounded-full bg-action animate-ping" />
            )}
          </button>
          <button
            onClick={() => setActiveTab("res")}
            className={`px-3 py-1.5 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 ${
              activeTab === "res"
                ? "border-action text-copy"
                : "border-transparent text-muted hover:text-copy"
            }`}
          >
            <Film className="w-3.5 h-3.5" />
            <span>Hasil Klip ({renderedClips.length})</span>
          </button>
          <button
            onClick={() => setActiveTab("eval")}
            className={`px-3 py-1.5 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 ${
              activeTab === "eval"
                ? "border-action text-copy"
                : "border-transparent text-muted hover:text-copy"
            }`}
          >
            <Award className="w-3.5 h-3.5" />
            <span>Golden Set</span>
          </button>
          <button
            onClick={() => setActiveTab("spec")}
            className={`px-3 py-1.5 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 ${
              activeTab === "spec"
                ? "border-action text-copy"
                : "border-transparent text-muted hover:text-copy"
            }`}
          >
            <Palette className="w-3.5 h-3.5" />
            <span>Spec & Palet</span>
          </button>
        </nav>

        {/* Live Running Timecode Counter */}
        <div className="font-mono text-xs font-bold tracking-wider text-muted select-none">
          {timecode}
        </div>
      </header>

      {/* Main Cutting Room Workspace */}
      <main className="max-w-[1280px] w-full mx-auto px-5 py-8 flex flex-col gap-8 flex-1">
        {/* VIEW 1: HOME */}
        {activeTab === "home" && (
          <div className="flex flex-col gap-10">
            {/* Clapper Slate Job Form */}
            <JobForm onSubmit={handleStartJob} loading={loading} />

            {/* Proyek Terakhir (Recent Projects) */}
            <div className="flex flex-col gap-4">
              <div className="flex items-baseline justify-between border-b border-line pb-2.5">
                <h2 className="text-xl font-extrabold uppercase tracking-tight text-copy">
                  PROYEK TERAKHIR
                </h2>
                <span className="text-xs text-muted font-mono">
                  {recentJobs.length} proyek tersimpan di server
                </span>
              </div>

              {recentJobs.length === 0 ? (
                <div className="p-8 bg-surface border border-line text-center text-xs text-muted">
                  Belum ada riwayat job. Mulai dengan memasukkan link YouTube di atas.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                  {recentJobs.map((j) => (
                    <div
                      key={j.id}
                      onClick={() => handleSelectRecentJob(j)}
                      className="marked-card p-4 bg-surface border border-line hover:border-action cursor-pointer transition-all flex flex-col justify-between gap-3 shadow-md"
                    >
                      <i className="crop-mark crop-tl" />
                      <i className="crop-mark crop-tr" />
                      <i className="crop-mark crop-bl" />
                      <i className="crop-mark crop-br" />

                      <div className="aspect-[16/9] bg-card border-x-4 border-dashed border-line p-3 flex flex-col justify-between relative overflow-hidden">
                        <div className="flex items-center justify-between">
                          <span className="text-[10px] font-mono font-bold bg-bg px-2 py-0.5 border border-line text-copy uppercase">
                            JOB: {j.id.slice(0, 8)}
                          </span>
                          <span
                            className={`text-[9px] font-bold px-1.5 py-0.5 border uppercase ${
                              j.status === "done"
                                ? "border-green-500/40 text-green-400 bg-green-500/10"
                                : j.status === "failed"
                                ? "border-err/40 text-err bg-err/10"
                                : "border-action/40 text-action bg-action/10"
                            }`}
                          >
                            {j.status}
                          </span>
                        </div>
                        <div className="font-extrabold text-sm text-copy line-clamp-2">
                          {j.title || j.source_url}
                        </div>
                        <div className="flex justify-between items-center text-[10px] font-mono text-muted">
                          <span>{j.genre.toUpperCase()}</span>
                          <span>{Math.round(j.progress * 100)}%</span>
                        </div>
                      </div>

                      <div className="flex items-center justify-between text-xs text-muted font-mono pt-1">
                        <span>{new Date(j.created_at).toLocaleDateString()}</span>
                        <div className="flex items-center gap-3">
                          <button
                            type="button"
                            onClick={(e) => handleDeleteJob(j.id, e)}
                            className="text-muted hover:text-err p-1 transition-colors flex items-center gap-1"
                            title="Hapus Proyek"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            <span className="text-[10px] hidden sm:inline">Hapus</span>
                          </button>
                          <span className="text-action font-bold flex items-center gap-1">
                            Buka Workspace <ArrowRight className="w-3 h-3" />
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* VIEW 2: PROCESSING & REVIEW */}
        {activeTab === "proc" && (
          <div className="flex flex-col gap-8">
            {/* Header info if job exists */}
            {currentJob ? (
              <>
                <ProgressTracker
                  job={currentJob}
                  onCancel={handleCancelJob}
                  onRetry={handleTriggerRender}
                  onDelete={() => handleDeleteJob(currentJob.id)}
                />

                {/* Multi-Lane Timeline */}
                {timeline && (
                  <TimelineVisualizer
                    timeline={timeline}
                    candidates={candidates}
                    selectedCandidateId={selectedCandId}
                    onSelectCandidate={setSelectedCandId}
                  />
                )}

                {/* Candidates Review */}
                {candidates.length > 0 && (
                  <div className="flex flex-col gap-4">
                    <div className="flex items-center justify-between border-b border-line pb-3 flex-wrap gap-3">
                      <div>
                        <h3 className="font-extrabold text-base md:text-lg uppercase tracking-tight text-copy">
                          KANDIDAT HIGHLIGHT ({candidates.length} MOMEN)
                        </h3>
                        <p className="text-xs text-muted">
                          Pilih dan kurasi momen terbaik sebelum dibakar ke video 9:16 dan subtitle kinetic.
                        </p>
                      </div>

                      <button
                        onClick={handleTriggerRender}
                        disabled={isRendering || currentJob.status === "rendering"}
                        className="btn-action flex items-center gap-2 px-6 py-3 text-xs md:text-sm font-bold text-bg disabled:opacity-50"
                      >
                        {isRendering || currentJob.status === "rendering" ? (
                          <>
                            <RefreshCw className="w-4 h-4 animate-spin" />
                            <span>SEDANG RENDERING...</span>
                          </>
                        ) : (
                          <>
                            <Play className="w-4 h-4 fill-bg" />
                            <span>
                              RENDER KANDIDAT TERPILIH ({keptCandidatesCount > 0 ? keptCandidatesCount : candidates.length})
                            </span>
                          </>
                        )}
                      </button>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                      {candidates.map((cand) => (
                        <CandidateCard
                          key={cand.id}
                          candidate={cand}
                          isSelected={cand.id === selectedCandId}
                          onSelect={() => setSelectedCandId(cand.id)}
                          onUpdateStatus={(st) => handleUpdateStatus(cand.id, st)}
                          onUpdateTiming={(s, e) => handleUpdateTiming(cand.id, s, e)}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="p-16 marked-frame bg-surface border border-line text-center flex flex-col items-center gap-3">
                <i className="crop-mark crop-tl" />
                <i className="crop-mark crop-tr" />
                <i className="crop-mark crop-bl" />
                <i className="crop-mark crop-br" />
                <Layers className="w-10 h-10 text-action" />
                <h3 className="text-copy font-bold text-base">Belum Ada Job Aktif</h3>
                <p className="text-muted text-xs max-w-sm">
                  Masukkan link YouTube pada tab Home untuk memulai pipeline deteksi sinyal dan kurasi highlight.
                </p>
                <button
                  onClick={() => setActiveTab("home")}
                  className="btn-action px-5 py-2 text-xs font-bold text-bg mt-2"
                >
                  KE TAB HOME
                </button>
              </div>
            )}
          </div>
        )}

        {/* VIEW 3: HASIL KLIP & SUBTITLE STUDIO */}
        {activeTab === "res" && (
          <div className="flex flex-col gap-8">
            {/* Header bar */}
            <div className="flex items-center justify-between border-b border-line pb-3 flex-wrap gap-4">
              <div>
                <h2 className="text-xl font-extrabold uppercase tracking-tight text-copy">
                  {renderedClips.length > 0
                    ? `${renderedClips.length} KLIP SIAP UPLOAD`
                    : "STUDIO KLIP & SUBTITLE"}
                </h2>
                <p className="text-xs text-muted">
                  Hasil render 9:16 vertikal dengan standar broadcast EBU R128 (-14 LUFS) dan subtitle kinetic ASS.
                </p>
              </div>

              {renderedClips.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-muted">
                    Total: {renderedClips.length} Klip
                  </span>
                </div>
              )}
            </div>

            {/* List of Rendered Clips Cards */}
            {renderedClips.length > 0 && (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                {renderedClips.map((c, idx) => (
                  <button
                    key={c.id}
                    onClick={() => handleLoadClip(c.id)}
                    className={`marked-card p-2.5 bg-surface border text-left flex flex-col gap-1.5 transition-all ${
                      activeClip?.id === c.id
                        ? "border-action bg-card ring-1 ring-action"
                        : "border-line hover:border-action/60"
                    }`}
                  >
                    <i className="crop-mark crop-tl" />
                    <i className="crop-mark crop-tr" />
                    <i className="crop-mark crop-bl" />
                    <i className="crop-mark crop-br" />

                    <div className="aspect-[9/12] bg-card border-x-2 border-dashed border-line flex items-center justify-center p-2 text-center">
                      <span className="font-extrabold text-sm text-copy font-mono">
                        CLIP #{idx + 1}
                      </span>
                    </div>
                    <div className="flex justify-between items-center text-[10px] font-mono text-muted">
                      <span>{c.duration_s?.toFixed(1) || "--"}s</span>
                      <span className={c.qa?.passed ? "text-green-400 font-bold" : "text-action"}>
                        {c.qa?.passed ? "QA PASS" : "RENDERED"}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}

            {/* Active Clip Player & Subtitle Studio */}
            {activeClip ? (
              <div className="flex flex-col gap-8">
                <ClipPlayer
                  clip={activeClip}
                  onEditSubtitles={() => setIsEditingSubtitles(!isEditingSubtitles)}
                />

                {isEditingSubtitles && activeSubtitleTrack && (
                  <SubtitleEditor
                    clipId={activeClip.id}
                    initialTrack={activeSubtitleTrack}
                    onClipUpdated={() => handleLoadClip(activeClip.id)}
                  />
                )}
              </div>
            ) : (
              <div className="p-16 marked-frame bg-surface border border-line text-center flex flex-col items-center gap-3">
                <i className="crop-mark crop-tl" />
                <i className="crop-mark crop-tr" />
                <i className="crop-mark crop-bl" />
                <i className="crop-mark crop-br" />
                <Video className="w-10 h-10 text-action" />
                <h3 className="text-copy font-bold text-base">Belum Ada Klip yang Dirender</h3>
                <p className="text-muted text-xs max-w-sm">
                  Pilih kandidat di tab Processing & Review lalu jalankan render untuk menghasilkan klip 9:16.
                </p>
                {currentJob && (
                  <button
                    onClick={() => setActiveTab("proc")}
                    className="btn-action px-5 py-2 text-xs font-bold text-bg mt-2"
                  >
                    KE PROCESSING & REVIEW
                  </button>
                )}
              </div>
            )}
          </div>
        )}

        {/* VIEW 4: GOLDEN SET BENCHMARK */}
        {activeTab === "eval" && <EvaluationView />}

        {/* VIEW 5: SPEC & DESIGN TOKENS */}
        {activeTab === "spec" && (
          <div className="marked-frame border border-line bg-surface p-6 shadow-2xl flex flex-col gap-8">
            <i className="crop-mark crop-tl" />
            <i className="crop-mark crop-tr" />
            <i className="crop-mark crop-bl" />
            <i className="crop-mark crop-br" />

            <div className="border-b border-line pb-3">
              <h2 className="text-xl font-extrabold uppercase tracking-tight text-copy">
                DESIGN SYSTEM • CUTTING ROOM
              </h2>
              <p className="text-xs text-muted">
                Palet warna datar, tanpa gradien halus, terinspirasi meja potong seluloid film analog.
              </p>
            </div>

            {/* Palet Warna */}
            <div className="flex flex-col gap-3">
              <h3 className="text-sm font-bold uppercase tracking-wider text-copy">Palet Warna</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3 font-mono text-xs">
                {[
                  { name: "Background", hex: "#0A0A0A" },
                  { name: "Surface", hex: "#141414" },
                  { name: "Card", hex: "#1C1C1C" },
                  { name: "Border", hex: "#2A2A2A" },
                  { name: "Orange", hex: "#FF6A00" },
                  { name: "Orange Hover", hex: "#FF8533" },
                  { name: "Teks Putih", hex: "#F5F5F5" },
                  { name: "Teks Redup", hex: "#9A9A9A" },
                ].map((c) => (
                  <div key={c.name} className="border border-line bg-card p-2 flex flex-col gap-2">
                    <div className="h-12 w-full border border-line/40" style={{ background: c.hex }} />
                    <div>
                      <div className="font-bold text-[11px] text-copy">{c.name}</div>
                      <div className="text-[10px] text-muted">{c.hex}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Elemen Khas Cutting Room */}
            <div className="flex flex-col gap-3 text-xs text-muted">
              <h3 className="text-sm font-bold uppercase tracking-wider text-copy">
                Elemen Khas Meja Potong
              </h3>
              <ul className="list-disc list-inside flex flex-col gap-2">
                <li>
                  <strong className="text-copy">Crop Marks:</strong> Setiap kartu memiliki siku 4 sudut berukuran 14px yang menyala oranye saat hover.
                </li>
                <li>
                  <strong className="text-copy">Film Perforations:</strong> Sisi kiri dan kanan thumbnail bergaris putus-putus menyerupai lubang roda seluloid film.
                </li>
                <li>
                  <strong className="text-copy">Skor Raksasa:</strong> Angka penilaian 88px–120px tabular oranye, sengaja diposisikan terpotong tepi sudut kartu.
                </li>
                <li>
                  <strong className="text-copy">Running Timecode:</strong> Ticker 24fps berjalan di header atas menyerupai timecode deck tape analog.
                </li>
                <li>
                  <strong className="text-copy">Clapper Slate:</strong> Container input berbentuk papan klaker sutradara dengan Scene, Take, dan tombol oranye bayangan offset solid.
                </li>
              </ul>
            </div>
          </div>
        )}
      </main>

      {/* Floating Bottom Toast */}
      {toastMessage && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 bg-copy text-bg px-5 py-2.5 text-xs font-bold shadow-2xl z-50 animate-bounce flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-action" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Footer */}
      <footer className="border-t border-line py-5 px-6 text-center text-xs text-muted bg-surface/50">
        <div className="max-w-[1280px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-3 font-mono">
          <span>CLIPFORGE v2.0 • CUTTING ROOM ENGINE</span>
          <span>LIBASS • EBU R128 • TARGETED FASTER-WHISPER • 9ROUTER LLM</span>
        </div>
      </footer>
    </div>
  );
}
