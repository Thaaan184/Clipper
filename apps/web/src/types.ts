export interface JobParams {
  clip_count?: number;
  reframe_mode?: "blur" | "center" | "stacked";
  subtitle_style?: string;
  min_duration_s?: number;
  max_duration_s?: number;
}

export interface Job {
  id: string;
  source_url: string;
  genre: string;
  language: string;
  params: JobParams;
  status:
    | "created"
    | "validating"
    | "fetching_signals"
    | "analyzing_signals"
    | "fusing_candidates"
    | "targeted_asr"
    | "scout_rerank"
    | "awaiting_review"
    | "rendering"
    | "done"
    | "failed"
    | "cancelled";
  progress: number;
  error_code?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CandidateEvidence {
  loud_surge_db?: number;
  chat_velocity?: number;
  heatmap_score?: number;
  onset_density?: number;
  speech_ratio?: number;
  nonspeech_ratio?: number;
  duration_s?: number;
}

export interface Candidate {
  id: string;
  job_id: string;
  rank: number;
  start_s: number;
  end_s: number;
  user_start_s?: number | null;
  user_end_s?: number | null;
  peak_s: number;
  signal_score: number;
  llm_score: number;
  final_score: number;
  category: string;
  title: string;
  hook_text: string;
  reason: string;
  evidence: CandidateEvidence;
  flags: string[];
  status: "proposed" | "kept" | "rejected" | "rendered";
}

export interface SignalPoint {
  time_s: number;
  value: number;
}

export interface TimelineData {
  job_id: string;
  duration_s: number;
  audio_energy: SignalPoint[];
  chat_velocity: SignalPoint[];
  heatmap: SignalPoint[];
  candidates: Candidate[];
}

export interface QAInfo {
  passed: boolean;
  checks: Record<string, boolean>;
  errors: string[];
  details?: Record<string, unknown>;
}

export interface Clip {
  id: string;
  candidate_id: string;
  job_id: string;
  status: "pending" | "rendering" | "done" | "failed";
  video_path?: string | null;
  thumb_path?: string | null;
  srt_path?: string | null;
  width: number;
  height: number;
  duration_s?: number | null;
  render_params: Record<string, unknown>;
  qa?: QAInfo | null;
  created_at: string;
}

export interface SubtitleWord {
  idx: number;
  start_s: number;
  end_s: number;
  text: string;
  confidence?: number;
}

export interface SubtitleTrack {
  clip_id: string;
  revision: number;
  words: SubtitleWord[];
  style: string;
  language?: string;
}
