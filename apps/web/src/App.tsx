import { useEffect, useState } from "react";
import {
  cancelJob,
  createJob,
  deleteFinishedClip,
  deleteJob,
  getCandidates,
  getClip,
  getClipSubtitles,
  getFinishedClipSrtUrl,
  getFinishedClipVideoUrl,
  getJob,
  getJobClips,
  getTimeline,
  listFinishedClips,
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
import {
  Candidate,
  Clip,
  FinishedClip,
  Job,
  JobParams,
  SubtitleTrack,
  TimelineData,
} from "./types";
import {
  ArrowRight,
  Award,
  CheckCircle,
  Download,
  Edit3,
  Film,
  Layers,
  Play,
  RefreshCw,
  Sparkles,
  Trash2,
  Video,
} from "lucide-react";

type NavTab = "home" | "proc" | "edit" | "res" | "eval";

interface ParsedRoute {
  tab: NavTab;
  projectId?: string;
  clipId?: string;
}

function parseUrlPath(pathname: string): ParsedRoute {
  if (pathname === "/results" || pathname === "/results/") {
    return { tab: "res" };
  }
  if (pathname === "/eval" || pathname === "/eval/") {
    return { tab: "eval" };
  }
  const editWithClipMatch = pathname.match(/^\/projects\/([^/]+)\/clips\/([^/]+)\/editing\/?$/);
  if (editWithClipMatch) {
    return { tab: "edit", projectId: editWithClipMatch[1], clipId: editWithClipMatch[2] };
  }
  const editMatch = pathname.match(/^\/projects\/([^/]+)\/editing\/?$/);
  if (editMatch) {
    return { tab: "edit", projectId: editMatch[1] };
  }
  if (pathname === "/editing" || pathname === "/editing/") {
    return { tab: "edit" };
  }
  const procMatch = pathname.match(/^\/projects\/([^/]+)\/processing\/?$/);
  if (procMatch) {
    return { tab: "proc", projectId: procMatch[1] };
  }
  if (pathname === "/processing" || pathname === "/processing/") {
    return { tab: "proc" };
  }
  return { tab: "home" };
}

export default function App(): JSX.Element {
  const [activeTab, setActiveTab] = useState<NavTab>("home");

  const [currentJob, setCurrentJob] = useState<Job | null>(null);
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedCandId, setSelectedCandId] = useState<string | null>(null);
  const [renderedClips, setRenderedClips] = useState<Clip[]>([]);
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);

  // Global repository of finished / saved clips
  const [finishedClips, setFinishedClips] = useState<FinishedClip[]>([]);

  // Active clip & subtitles for Editing tab
  const [activeClip, setActiveClip] = useState<Clip | null>(null);
  const [activeSubtitleTrack, setActiveSubtitleTrack] = useState<SubtitleTrack | null>(null);

  const [loading, setLoading] = useState(false);
  const [isRendering, setIsRendering] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
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

  const navigateTo = (
    tab: NavTab,
    projectId?: string,
    clipId?: string,
    replace = false
  ) => {
    let targetPath = "/";
    if (tab === "home") {
      targetPath = "/";
    } else if (tab === "proc") {
      targetPath = projectId ? `/projects/${projectId}/processing` : "/";
    } else if (tab === "edit") {
      if (projectId && clipId) {
        targetPath = `/projects/${projectId}/clips/${clipId}/editing`;
      } else if (projectId) {
        targetPath = `/projects/${projectId}/editing`;
      } else {
        targetPath = "/editing";
      }
    } else if (tab === "res") {
      targetPath = "/results";
    } else if (tab === "eval") {
      targetPath = "/eval";
    }

    if (window.location.pathname !== targetPath) {
      if (replace) {
        window.history.replaceState(null, "", targetPath);
      } else {
        window.history.pushState(null, "", targetPath);
      }
    }

    setActiveTab(tab);
    if (projectId) {
      localStorage.setItem("clipforge_active_job_id", projectId);
    }
    if (clipId) {
      localStorage.setItem("clipforge_active_clip_id", clipId);
    }
  };

  // Load recent jobs
  const loadRecentJobs = async () => {
    try {
      const list = await listJobs(12);
      setRecentJobs(list);
    } catch {
      // ignore
    }
  };

  // Load global finished clips
  const loadFinishedClipsList = async () => {
    try {
      const list = await listFinishedClips();
      setFinishedClips(list);
    } catch {
      // ignore
    }
  };

  // Route Synchronization on mount and back/forward navigation
  const syncFromRoute = async () => {
    const route = parseUrlPath(window.location.pathname);
    setActiveTab(route.tab);

    const fallbackJobId = localStorage.getItem("clipforge_active_job_id");
    const fallbackClipId = localStorage.getItem("clipforge_active_clip_id");
    const targetJobId =
      route.projectId ||
      (route.tab === "proc" || route.tab === "edit" ? fallbackJobId : null);
    const targetClipId =
      route.clipId || (route.tab === "edit" ? fallbackClipId : null);

    if (targetJobId) {
      try {
        const job = await getJob(targetJobId);
        setCurrentJob(job);
        const [tData, cData, clipsRes] = await Promise.all([
          getTimeline(job.id).catch(() => null),
          getCandidates(job.id).catch(() => ({ candidates: [] })),
          getJobClips(job.id).catch(() => ({ clips: [] })),
        ]);
        if (tData) setTimeline(tData);
        if (cData) setCandidates(cData.candidates);
        if (clipsRes && clipsRes.clips.length > 0) {
          setRenderedClips(clipsRes.clips);
          const matchClip = targetClipId
            ? clipsRes.clips.find((c: Clip) => c.id === targetClipId)
            : null;
          const chosen = matchClip || clipsRes.clips[0];
          setActiveClip(chosen);
          try {
            const subs = await getClipSubtitles(chosen.id);
            setActiveSubtitleTrack(subs);
          } catch {
            // ignore
          }
        }
      } catch (err) {
        console.error("Failed to restore routed job:", err);
      }
    }

    if (route.tab === "res") {
      loadFinishedClipsList();
    }
  };

  useEffect(() => {
    loadRecentJobs();
    loadFinishedClipsList();
    syncFromRoute();

    const handlePopState = () => {
      syncFromRoute();
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  // Poll current job when in progress
  useEffect(() => {
    if (!currentJob) return;
    const isTerminal = ["done", "failed", "cancelled"].includes(currentJob.status);

    const fetchDetails = async (jobId: string) => {
      try {
        const updated = await getJob(jobId);
        setCurrentJob(updated);

        if (["awaiting_review", "rendering", "done"].includes(updated.status)) {
          const [tData, cData] = await Promise.all([
            getTimeline(updated.id).catch(() => null),
            getCandidates(updated.id).catch(() => ({ candidates: [] })),
          ]);
          if (tData) setTimeline(tData);
          if (cData) setCandidates(cData.candidates);
        }

        if (["rendering", "done"].includes(updated.status)) {
          const clipsRes = await getJobClips(updated.id).catch(() => ({ clips: [] }));
          if (clipsRes && clipsRes.clips.length > 0) {
            setRenderedClips(clipsRes.clips);
            if (!activeClip) {
              const first = clipsRes.clips[0];
              setActiveClip(first);
              getClipSubtitles(first.id)
                .then(setActiveSubtitleTrack)
                .catch(() => {});
            }
          }
        }
      } catch (err) {
        console.error("Failed to poll job:", err);
      }
    };

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
      navigateTo("proc", job.id);
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
    setActiveClip(null);
    setActiveSubtitleTrack(null);
    navigateTo("proc", job.id);
    showToast(`Memuat data proyek ${job.id.slice(0, 8)}`);
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
        const first = clipsRes.clips[0];
        setActiveClip(first);
        getClipSubtitles(first.id)
          .then(setActiveSubtitleTrack)
          .catch(() => {});
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
    setIsDeleting(true);
    try {
      await deleteJob(jobId);
      setRecentJobs((prev) => prev.filter((j) => j.id !== jobId));
      if (currentJob?.id === jobId) {
        setCurrentJob(null);
        setTimeline(null);
        setCandidates([]);
        setRenderedClips([]);
        setActiveClip(null);
        setActiveSubtitleTrack(null);
        localStorage.removeItem("clipforge_active_job_id");
        localStorage.removeItem("clipforge_active_clip_id");
        navigateTo("home");
      }
      showToast("Proyek berhasil dihapus.");
      loadFinishedClipsList();
    } catch (err: any) {
      showToast(`Gagal menghapus proyek: ${err.message || err}`);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDeleteFinishedClip = async (clipId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    if (!confirm("Hapus klip ini secara permanen dari Hasil Klip?")) {
      return;
    }
    try {
      await deleteFinishedClip(clipId);
      setFinishedClips((prev) => prev.filter((fc) => fc.clip_id !== clipId && fc.id !== clipId));
      showToast("Klip berhasil dihapus dari Hasil Klip.");
    } catch (err: any) {
      showToast(`Gagal menghapus klip: ${err.message || err}`);
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

  const handleSelectClipForEditing = async (clip: Clip) => {
    setActiveClip(clip);
    try {
      const subs = await getClipSubtitles(clip.id);
      setActiveSubtitleTrack(subs);
    } catch {
      setActiveSubtitleTrack(null);
    }
    navigateTo("edit", currentJob?.id || clip.job_id, clip.id);
    showToast(`Membuka klip ${clip.id.slice(0, 8)} di Studio Editing`);
  };

  const handleOpenFinishedInEditor = async (fc: FinishedClip) => {
    try {
      if (fc.job_id) {
        const job = await getJob(fc.job_id).catch(() => null);
        if (job) {
          setCurrentJob(job);
          const clipsRes = await getJobClips(job.id).catch(() => ({ clips: [] }));
          setRenderedClips(clipsRes.clips);
        }
      }
      const clip = await getClip(fc.clip_id);
      setActiveClip(clip);
      const subs = await getClipSubtitles(fc.clip_id);
      setActiveSubtitleTrack(subs);
      navigateTo("edit", fc.job_id || "global", fc.clip_id);
      showToast(`Membuka klip ${fc.clip_id.slice(0, 8)} di Editor`);
    } catch (err: any) {
      showToast(`Gagal membuka klip di editor: ${err.message || err}`);
    }
  };

  const handleReloadCurrentClip = async () => {
    if (!activeClip) return;
    try {
      const updatedClip = await getClip(activeClip.id);
      setActiveClip(updatedClip);
      const subs = await getClipSubtitles(activeClip.id);
      setActiveSubtitleTrack(subs);
      loadFinishedClipsList();
    } catch {
      // ignore
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
          onClick={() => navigateTo("home")}
        >
          <div className="w-3.5 h-3.5 bg-action" />
          <div className="flex items-baseline gap-2">
            <span className="font-extrabold text-base tracking-[0.16em] uppercase text-copy">
              CLIPFORGE
            </span>
            <span className="text-[10px] font-mono font-bold text-action">v2</span>
          </div>
        </div>

        {/* Navigation Tabs: Home -> Processing & Review -> Editing -> Hasil Klip */}
        <nav className="flex items-center gap-1 sm:gap-2">
          {/* TAB 1: HOME */}
          <button
            onClick={() => navigateTo("home")}
            className={`px-3 py-1.5 text-xs font-bold transition-all border-b-2 ${
              activeTab === "home"
                ? "border-action text-copy"
                : "border-transparent text-muted hover:text-copy"
            }`}
          >
            Home
          </button>

          {/* TAB 2: PROCESSING & REVIEW */}
          <button
            onClick={() => navigateTo("proc", currentJob?.id)}
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

          {/* TAB 3: EDITING */}
          <button
            onClick={() => navigateTo("edit", currentJob?.id, activeClip?.id)}
            className={`px-3 py-1.5 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 ${
              activeTab === "edit"
                ? "border-action text-copy"
                : "border-transparent text-muted hover:text-copy"
            }`}
          >
            <Edit3 className="w-3.5 h-3.5" />
            <span>Editing</span>
            {activeClip && (
              <span className="text-[10px] font-mono px-1 py-0.2 bg-card border border-line text-action">
                #{activeClip.id.slice(0, 4)}
              </span>
            )}
          </button>

          {/* TAB 4: HASIL KLIP (GLOBAL) */}
          <button
            onClick={() => {
              loadFinishedClipsList();
              navigateTo("res");
            }}
            className={`px-3 py-1.5 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 ${
              activeTab === "res"
                ? "border-action text-copy"
                : "border-transparent text-muted hover:text-copy"
            }`}
          >
            <Film className="w-3.5 h-3.5" />
            <span>Hasil Klip ({finishedClips.length})</span>
          </button>

          {/* GOLDEN SET BENCHMARK */}
          <button
            onClick={() => navigateTo("eval")}
            className={`px-3 py-1.5 text-xs font-bold transition-all border-b-2 flex items-center gap-1.5 ${
              activeTab === "eval"
                ? "border-action text-copy"
                : "border-transparent text-muted hover:text-copy"
            }`}
          >
            <Award className="w-3.5 h-3.5" />
            <span>Golden Set</span>
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
                            disabled={isDeleting}
                            onClick={(e) => handleDeleteJob(j.id, e)}
                            className="text-muted hover:text-err p-1 transition-colors flex items-center gap-1 disabled:opacity-50"
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

        {/* VIEW 2: PROCESSING & REVIEW (BOUND TO CURRENT PROJECT) */}
        {activeTab === "proc" && (
          <div className="flex flex-col gap-8">
            {currentJob ? (
              <>
                <ProgressTracker
                  job={currentJob}
                  onCancel={handleCancelJob}
                  onRetry={handleTriggerRender}
                  onDelete={() => handleDeleteJob(currentJob.id)}
                />

                {/* Rendered Clips Gallery for this project */}
                {renderedClips.length > 0 && (
                  <div className="marked-frame border border-line bg-surface p-5 flex flex-col gap-4">
                    <i className="crop-mark crop-tl" />
                    <i className="crop-mark crop-tr" />
                    <i className="crop-mark crop-bl" />
                    <i className="crop-mark crop-br" />
                    <div className="flex items-center justify-between border-b border-line pb-2.5">
                      <div className="flex items-center gap-2">
                        <Video className="w-4 h-4 text-action" />
                        <h3 className="font-extrabold text-sm uppercase tracking-wider text-copy">
                          KLIP BERHASIL DIRENDER ({renderedClips.length} KLIP)
                        </h3>
                      </div>
                      <span className="text-xs text-muted font-mono">
                        Pilih klip di bawah untuk mengedit teks & subtitle kinetic
                      </span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
                      {renderedClips.map((c, idx) => (
                        <button
                          key={c.id}
                          onClick={() => handleSelectClipForEditing(c)}
                          className={`marked-card p-2.5 bg-card border text-left flex flex-col gap-1.5 transition-all ${
                            activeClip?.id === c.id
                              ? "border-action ring-1 ring-action"
                              : "border-line hover:border-action/60"
                          }`}
                        >
                          <div className="aspect-[9/12] bg-bg border-x-2 border-dashed border-line flex flex-col items-center justify-center p-2 text-center">
                            <span className="font-extrabold text-sm text-copy font-mono">
                              KLIP #{idx + 1}
                            </span>
                            <span className="text-[10px] text-muted font-mono mt-1">
                              {c.id.slice(0, 6)}
                            </span>
                          </div>
                          <div className="flex justify-between items-center text-[10px] font-mono text-muted">
                            <span>{c.duration_s?.toFixed(1) || "--"}s</span>
                            <span className="text-action font-bold flex items-center gap-0.5">
                              Edit <ArrowRight className="w-2.5 h-2.5" />
                            </span>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

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
                <h3 className="text-copy font-bold text-base">Belum Ada Proyek Aktif</h3>
                <p className="text-muted text-xs max-w-sm">
                  Pilih proyek dari daftar Proyek Terakhir atau masukkan URL YouTube baru di tab Home.
                </p>
                <button
                  onClick={() => navigateTo("home")}
                  className="btn-action px-5 py-2 text-xs font-bold text-bg mt-2"
                >
                  KE TAB HOME
                </button>
              </div>
            )}
          </div>
        )}

        {/* VIEW 3: EDITING (BOUND TO CURRENT PROJECT & CLIP) */}
        {activeTab === "edit" && (
          <div className="flex flex-col gap-6">
            {/* Project & Clip Header */}
            <div className="flex items-center justify-between border-b border-line pb-3 flex-wrap gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <Edit3 className="w-5 h-5 text-action" />
                  <h2 className="text-xl font-extrabold uppercase tracking-tight text-copy">
                    STUDIO EDITING KLIP & SUBTITLE
                  </h2>
                </div>
                <p className="text-xs text-muted">
                  {currentJob
                    ? `Proyek: ${currentJob.title || currentJob.source_url} (JOB: ${currentJob.id.slice(0, 8)})`
                    : "Pilih klip untuk menyunting transkrip ASR, gaya subtitle kinetic ASS, dan render ulang."}
                </p>
              </div>

              {renderedClips.length > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs font-mono text-muted">Pilih Klip:</span>
                  {renderedClips.map((c, i) => (
                    <button
                      key={c.id}
                      onClick={() => handleSelectClipForEditing(c)}
                      className={`px-3 py-1 text-xs font-mono font-bold border transition-all ${
                        activeClip?.id === c.id
                          ? "bg-action text-bg border-action"
                          : "bg-surface text-copy border-line hover:border-action"
                      }`}
                    >
                      #{i + 1} ({c.duration_s?.toFixed(0)}s)
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Editing Workspace */}
            {activeClip ? (
              <div className="flex flex-col gap-8">
                {/* 9:16 Video Player Card */}
                <ClipPlayer
                  clip={activeClip}
                  onEditSubtitles={() => {}}
                />

                {/* Subtitle & Preset Studio */}
                {activeSubtitleTrack && (
                  <SubtitleEditor
                    clipId={activeClip.id}
                    initialTrack={activeSubtitleTrack}
                    onClipUpdated={handleReloadCurrentClip}
                  />
                )}
              </div>
            ) : currentJob && renderedClips.length > 0 ? (
              <div className="p-12 marked-frame bg-surface border border-line text-center flex flex-col items-center gap-3">
                <Video className="w-8 h-8 text-action" />
                <h3 className="text-copy font-bold text-sm">Pilih Klip untuk Diedit</h3>
                <p className="text-muted text-xs">
                  Proyek ini memiliki {renderedClips.length} klip. Klik tombol nomor klip di kanan atas untuk mulai mengedit.
                </p>
              </div>
            ) : currentJob ? (
              <div className="p-16 marked-frame bg-surface border border-line text-center flex flex-col items-center gap-3">
                <Video className="w-10 h-10 text-action" />
                <h3 className="text-copy font-bold text-base">Belum Ada Klip yang Dirender</h3>
                <p className="text-muted text-xs max-w-sm">
                  Pilih kandidat highlight di tab Processing & Review lalu jalankan render untuk menghasilkan klip 9:16.
                </p>
                <button
                  onClick={() => navigateTo("proc", currentJob.id)}
                  className="btn-action px-5 py-2 text-xs font-bold text-bg mt-2"
                >
                  KE PROCESSING & REVIEW
                </button>
              </div>
            ) : (
              <div className="p-16 marked-frame bg-surface border border-line text-center flex flex-col items-center gap-3">
                <Layers className="w-10 h-10 text-action" />
                <h3 className="text-copy font-bold text-base">Belum Ada Proyek Dipilih</h3>
                <p className="text-muted text-xs max-w-sm">
                  Buka tab Home atau pilih proyek dari riwayat untuk masuk ke studio editing klip.
                </p>
                <button
                  onClick={() => navigateTo("home")}
                  className="btn-action px-5 py-2 text-xs font-bold text-bg mt-2"
                >
                  KE TAB HOME
                </button>
              </div>
            )}
          </div>
        )}

        {/* VIEW 4: HASIL KLIP (GLOBAL / PERMANENT ALL PROJECTS) */}
        {activeTab === "res" && (
          <div className="flex flex-col gap-8">
            <div className="flex items-center justify-between border-b border-line pb-3 flex-wrap gap-4">
              <div>
                <div className="flex items-center gap-2">
                  <Film className="w-5 h-5 text-action" />
                  <h2 className="text-xl font-extrabold uppercase tracking-tight text-copy">
                    HASIL KLIP GLOBAL ({finishedClips.length} KLIP)
                  </h2>
                </div>
                <p className="text-xs text-muted">
                  Katalog permanen seluruh klip final yang sudah diedit dan disimpan dari semua proyek.
                </p>
              </div>

              <button
                onClick={loadFinishedClipsList}
                className="btn-ghost flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono font-bold"
              >
                <RefreshCw className="w-3.5 h-3.5 text-action" />
                <span>REFRESH KATALOG</span>
              </button>
            </div>

            {finishedClips.length === 0 ? (
              <div className="p-16 marked-frame bg-surface border border-line text-center flex flex-col items-center gap-3">
                <i className="crop-mark crop-tl" />
                <i className="crop-mark crop-tr" />
                <i className="crop-mark crop-bl" />
                <i className="crop-mark crop-br" />
                <Film className="w-10 h-10 text-action opacity-60" />
                <h3 className="text-copy font-bold text-base">Belum Ada Klip Tersimpan</h3>
                <p className="text-muted text-xs max-w-sm">
                  Render klip di Processing & Review atau simpan revisi subtitle di tab Editing untuk menyimpannya ke Hasil Klip permanen.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {finishedClips.map((fc) => {
                  const videoUrl = getFinishedClipVideoUrl(fc.clip_id || fc.id);
                  const srtUrl = getFinishedClipSrtUrl(fc.clip_id || fc.id);
                  let wordsPreview = "";
                  try {
                    if (fc.subtitles_json) {
                      const words = JSON.parse(fc.subtitles_json);
                      wordsPreview = words.slice(0, 10).map((w: any) => w.text).join(" ");
                    }
                  } catch {
                    // ignore
                  }

                  return (
                    <div
                      key={fc.id}
                      className="marked-card p-4 bg-surface border border-line hover:border-action/60 transition-all flex flex-col justify-between gap-4 shadow-xl"
                    >
                      <i className="crop-mark crop-tl" />
                      <i className="crop-mark crop-tr" />
                      <i className="crop-mark crop-bl" />
                      <i className="crop-mark crop-br" />

                      {/* Video Player 9:16 */}
                      <div className="w-full aspect-[9/16] bg-bg border-x-4 border-dashed border-line relative overflow-hidden flex items-center justify-center">
                        <video
                          src={videoUrl}
                          controls
                          playsInline
                          preload="metadata"
                          className="w-full h-full object-contain"
                        />
                      </div>

                      {/* Metadata */}
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center justify-between text-[10px] font-mono text-muted">
                          <span className="font-bold text-action truncate max-w-[200px]">
                            {fc.project_title || "ClipForge Proyek"}
                          </span>
                          <span>{fc.duration_s?.toFixed(1) || "--"}s</span>
                        </div>

                        {wordsPreview && (
                          <p className="text-xs text-muted line-clamp-2 italic bg-card p-2 border border-line/60">
                            &ldquo;{wordsPreview}...&rdquo;
                          </p>
                        )}

                        <div className="flex items-center justify-between text-[10px] font-mono text-muted pt-1 border-t border-line">
                          <span>{new Date(fc.updated_at).toLocaleDateString()}</span>
                          <span className="text-green-400 font-bold flex items-center gap-1">
                            <CheckCircle className="w-3 h-3" /> SIAP UPLOAD
                          </span>
                        </div>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center justify-between gap-2 pt-2 border-t border-line text-xs font-mono">
                        <button
                          onClick={() => handleOpenFinishedInEditor(fc)}
                          className="btn-action flex items-center gap-1 px-3 py-1.5 text-[11px] font-bold text-bg"
                        >
                          <Edit3 className="w-3 h-3" />
                          <span>Edit Ulang</span>
                        </button>

                        <div className="flex items-center gap-1.5">
                          <a
                            href={srtUrl}
                            download={`clip-${(fc.clip_id || fc.id).slice(0, 8)}.srt`}
                            className="btn-ghost p-1.5 text-copy hover:text-action"
                            title="Download SRT"
                          >
                            <Download className="w-3.5 h-3.5" />
                          </a>
                          <a
                            href={videoUrl}
                            download={`clip-${(fc.clip_id || fc.id).slice(0, 8)}.mp4`}
                            className="btn-ghost p-1.5 text-copy hover:text-action"
                            title="Download MP4"
                          >
                            <Video className="w-3.5 h-3.5" />
                          </a>
                          <button
                            onClick={(e) => handleDeleteFinishedClip(fc.clip_id || fc.id, e)}
                            className="btn-ghost p-1.5 text-muted hover:text-err"
                            title="Hapus dari Hasil Klip"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* VIEW 5: GOLDEN SET BENCHMARK */}
        {activeTab === "eval" && <EvaluationView />}
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
