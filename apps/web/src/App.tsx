import { useEffect, useState } from "react";
import {
  cancelJob,
  createJob,
  getCandidates,
  getClip,
  getClipSubtitles,
  getJob,
  getTimeline,
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
  Award,
  Film,
  Layers,
  Play,
  Sparkles,
} from "lucide-react";

export default function App(): JSX.Element {
  const [activeTab, setActiveTab] = useState<"pipeline" | "clips" | "eval">("pipeline");

  const [currentJob, setCurrentJob] = useState<Job | null>(null);
  const [timeline, setTimeline] = useState<TimelineData | null>(null);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selectedCandId, setSelectedCandId] = useState<string | null>(null);

  const [activeClip, setActiveClip] = useState<Clip | null>(null);
  const [activeSubtitleTrack, setActiveSubtitleTrack] = useState<SubtitleTrack | null>(null);
  const [isEditingSubtitles, setIsEditingSubtitles] = useState(false);

  const [loading, setLoading] = useState(false);
  const [isRendering, setIsRendering] = useState(false);

  // Poll current job when active
  useEffect(() => {
    if (!currentJob) return;
    const isTerminal = ["done", "failed", "cancelled"].includes(currentJob.status);
    if (isTerminal) return;

    const interval = setInterval(async () => {
      try {
        const updated = await getJob(currentJob.id);
        setCurrentJob(updated);

        // Fetch candidates and timeline when reaching review or further
        if (
          ["awaiting_review", "rendering", "done"].includes(updated.status)
        ) {
          const [tData, cData] = await Promise.all([
            getTimeline(updated.id).catch(() => null),
            getCandidates(updated.id).catch(() => ({ candidates: [] })),
          ]);
          if (tData) setTimeline(tData);
          if (cData) setCandidates(cData.candidates);
        }
      } catch (err) {
        console.error("Failed to poll job:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [currentJob]);

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
      setActiveClip(null);
      setActiveSubtitleTrack(null);
    } catch (err) {
      alert(`Gagal membuat job: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  const handleCancelJob = async () => {
    if (!currentJob) return;
    try {
      await cancelJob(currentJob.id);
      setCurrentJob({ ...currentJob, status: "cancelled" });
    } catch (err) {
      alert(`Gagal membatalkan job: ${err}`);
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
    } catch (err) {
      alert(`Gagal update status kandidat: ${err}`);
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
    } catch (err) {
      alert(`Gagal update batas kandidat: ${err}`);
    }
  };

  const handleTriggerRender = async () => {
    if (!currentJob) return;
    setIsRendering(true);
    try {
      await triggerRender(currentJob.id);
      setCurrentJob({ ...currentJob, status: "rendering" });
      alert("Render batch dimulai untuk kandidat lolos kurasi!");
    } catch (err) {
      alert(`Gagal trigger render: ${err}`);
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
      setActiveTab("clips");
      setIsEditingSubtitles(false);
    } catch (err) {
      alert(`Gagal memuat clip: ${err}`);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex flex-col">
      {/* Top Navbar */}
      <header className="border-b border-zinc-800 bg-zinc-900/80 backdrop-blur sticky top-0 z-50 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-orange-600 flex items-center justify-center font-black text-white shadow-lg shadow-orange-600/30">
              CF
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-extrabold tracking-tight text-white text-lg">
                  ClipForge
                </h1>
                <span className="text-[10px] px-1.5 py-0.5 rounded font-mono font-bold bg-orange-500/20 text-orange-400 border border-orange-500/30">
                  v2 SIGNAL-FIRST
                </span>
              </div>
              <p className="text-zinc-400 text-xs">
                Signal-First, LLM-Last Gaming Video Clipper
              </p>
            </div>
          </div>

          {/* Tab Navigation */}
          <nav className="flex items-center gap-2 bg-zinc-950 p-1 rounded-xl border border-zinc-800">
            <button
              onClick={() => setActiveTab("pipeline")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                activeTab === "pipeline"
                  ? "bg-orange-600 text-white shadow-md"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <Layers className="w-4 h-4" />
              Pipeline & Review
            </button>
            <button
              onClick={() => setActiveTab("clips")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                activeTab === "clips"
                  ? "bg-orange-600 text-white shadow-md"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <Film className="w-4 h-4" />
              Player & Subtitles
            </button>
            <button
              onClick={() => setActiveTab("eval")}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all ${
                activeTab === "eval"
                  ? "bg-orange-600 text-white shadow-md"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              <Award className="w-4 h-4" />
              Golden Set Benchmark
            </button>
          </nav>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl w-full mx-auto p-6 flex flex-col gap-8 flex-1">
        {activeTab === "pipeline" && (
          <div className="flex flex-col gap-8">
            {/* Input Form */}
            <JobForm onSubmit={handleStartJob} loading={loading} />

            {/* Live Progress */}
            {currentJob && (
              <ProgressTracker job={currentJob} onCancel={handleCancelJob} />
            )}

            {/* Timeline Visualizer */}
            {timeline && (
              <TimelineVisualizer
                timeline={timeline}
                candidates={candidates}
                selectedCandidateId={selectedCandId}
                onSelectCandidate={setSelectedCandId}
              />
            )}

            {/* Candidate Review Grid */}
            {candidates.length > 0 && (
              <div className="flex flex-col gap-4">
                <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-orange-500" />
                    <h3 className="font-bold text-white text-base">
                      Kandidat Highlight ({candidates.length} Momen)
                    </h3>
                  </div>

                  <button
                    onClick={handleTriggerRender}
                    disabled={isRendering}
                    className="flex items-center gap-2 px-5 py-2.5 bg-orange-600 hover:bg-orange-500 disabled:opacity-50 text-white font-bold text-xs rounded-xl shadow-lg transition-all"
                  >
                    <Play className="w-4 h-4 fill-white" />
                    {isRendering ? "Memulai Render..." : "Render Kandidat Terpilih"}
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
          </div>
        )}

        {activeTab === "clips" && (
          <div className="flex flex-col gap-8">
            {activeClip ? (
              <>
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
              </>
            ) : (
              <div className="p-16 bg-zinc-900 border border-zinc-800 rounded-2xl flex flex-col items-center justify-center text-center gap-3">
                <Film className="w-12 h-12 text-zinc-600 animate-pulse" />
                <h3 className="text-white font-bold text-base">
                  Belum Ada Clip yang Dipilih
                </h3>
                <p className="text-zinc-400 text-xs max-w-sm">
                  Render kandidat dari tab &ldquo;Pipeline & Review&rdquo; terlebih dahulu, lalu pilih clip untuk memutar video atau mengedit subtitle secara visual.
                </p>
              </div>
            )}
          </div>
        )}

        {activeTab === "eval" && <EvaluationView />}
      </main>

      {/* Footer */}
      <footer className="border-t border-zinc-800 py-6 px-6 text-center text-xs text-zinc-500">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
          <span>ClipForge v2.0.0 — Signal-First, LLM-Last Architecture</span>
          <span className="font-mono text-zinc-400">
            Libass Deterministic • EBU R128 • Faster-Whisper Targeted
          </span>
        </div>
      </footer>
    </div>
  );
}
