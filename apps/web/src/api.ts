import {
  Candidate,
  Clip,
  FinishedClip,
  Job,
  JobParams,
  SubtitleTrack,
  SubtitleWord,
  TimelineData,
} from "./types";

const API_BASE = "";

export async function createJob(
  sourceUrl: string,
  genre = "gaming",
  language = "id",
  params?: JobParams
): Promise<Job> {
  const res = await fetch(`${API_BASE}/api/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      source_url: sourceUrl,
      genre,
      language,
      params,
    }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to create job" }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function getJob(jobId: string): Promise<Job> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch job ${jobId}`);
  }
  return res.json();
}

export async function listJobs(limit = 10): Promise<Job[]> {
  const res = await fetch(`${API_BASE}/api/jobs?limit=${limit}`);
  if (!res.ok) {
    throw new Error("Failed to list jobs");
  }
  return res.json();
}

export async function getJobClips(
  jobId: string
): Promise<{ clips: Clip[]; total: number }> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/clips`);
  if (!res.ok) {
    throw new Error(`Failed to fetch clips for job ${jobId}`);
  }
  return res.json();
}


export async function cancelJob(jobId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/cancel`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Failed to cancel job ${jobId}`);
  }
}

export async function deleteJob(jobId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(`Failed to delete job ${jobId}`);
  }
}

export async function getTimeline(jobId: string): Promise<TimelineData> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/timeline`);
  if (!res.ok) {
    throw new Error(`Failed to fetch timeline for job ${jobId}`);
  }
  return res.json();
}

export async function getCandidates(
  jobId: string
): Promise<{ candidates: Candidate[]; total: number }> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/candidates`);
  if (!res.ok) {
    throw new Error(`Failed to fetch candidates for job ${jobId}`);
  }
  return res.json();
}

export async function updateCandidate(
  candidateId: string,
  payload: {
    status?: "proposed" | "kept" | "rejected";
    user_start_s?: number;
    user_end_s?: number;
  }
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/jobs/candidates/${candidateId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`Failed to update candidate ${candidateId}`);
  }
}

export async function triggerRender(
  jobId: string,
  payload?: {
    candidate_ids?: string[];
    reframe_mode?: string;
    subtitle_style?: string;
  }
): Promise<{ status: string; job_id: string; message?: string }> {
  const res = await fetch(`${API_BASE}/api/jobs/${jobId}/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Failed to trigger render" }));
    throw new Error(err.detail || `Failed to trigger render for job ${jobId}`);
  }
  return res.json();
}

export async function getClip(clipId: string): Promise<Clip> {
  const res = await fetch(`${API_BASE}/api/clips/${clipId}`);
  if (!res.ok) {
    throw new Error(`Failed to fetch clip ${clipId}`);
  }
  return res.json();
}

export async function getClipSubtitles(clipId: string): Promise<SubtitleTrack> {
  const res = await fetch(`${API_BASE}/api/clips/${clipId}/subtitles`);
  if (!res.ok) {
    throw new Error(`Failed to fetch subtitles for clip ${clipId}`);
  }
  return res.json();
}

export async function updateClipSubtitles(
  clipId: string,
  words: SubtitleWord[],
  stylePreset: string | { preset?: string }
): Promise<{ revision: number }> {
  const presetStr =
    typeof stylePreset === "string"
      ? stylePreset
      : stylePreset?.preset || "classic_white";

  const res = await fetch(`${API_BASE}/api/clips/${clipId}/subtitles`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      words,
      style_preset: presetStr,
    }),
  });
  if (!res.ok) {
    throw new Error(`Failed to update subtitles for clip ${clipId}`);
  }
  return res.json();
}

export async function previewSubtitleFrame(
  clipId: string,
  t_s: number,
  stylePreset: string | { preset?: string },
  reframeMode = "blur",
  words?: SubtitleWord[]
): Promise<Blob> {
  const presetStr =
    typeof stylePreset === "string"
      ? stylePreset
      : stylePreset?.preset || "classic_white";

  const res = await fetch(`${API_BASE}/api/clips/${clipId}/subtitles/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      t_s,
      style_preset: presetStr,
      reframe_mode: reframeMode,
      words,
    }),
  });
  if (!res.ok) {
    throw new Error(`Failed to render subtitle frame preview`);
  }
  return res.blob();
}

export async function rerenderClip(clipId: string): Promise<Clip> {
  const res = await fetch(`${API_BASE}/api/clips/${clipId}/rerender`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Failed to rerender clip ${clipId}`);
  }
  return res.json();
}

export async function saveFinishedClip(clipId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/clips/${clipId}/save`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Failed to save finished clip ${clipId}`);
  }
  return res.json();
}

export async function listFinishedClips(): Promise<FinishedClip[]> {
  const res = await fetch(`${API_BASE}/api/clips/finished`);
  if (!res.ok) {
    throw new Error(`Failed to list finished clips`);
  }
  return res.json();
}

export async function deleteFinishedClip(clipId: string): Promise<any> {
  const res = await fetch(`${API_BASE}/api/clips/finished/${clipId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    throw new Error(`Failed to delete finished clip ${clipId}`);
  }
  return res.json();
}

export async function listAllClips(limit = 50): Promise<Clip[]> {
  const res = await fetch(`${API_BASE}/api/clips?limit=${limit}`);
  if (!res.ok) {
    throw new Error(`Failed to list all clips`);
  }
  return res.json();
}

export function getClipVideoUrl(clipId: string): string {
  return `${API_BASE}/api/clips/${clipId}/video`;
}

export function getClipSrtUrl(clipId: string): string {
  return `${API_BASE}/api/clips/${clipId}/subtitles.srt`;
}

export function getFinishedClipVideoUrl(clipId: string): string {
  return `${API_BASE}/api/clips/finished/${clipId}/video`;
}

export function getFinishedClipSrtUrl(clipId: string): string {
  return `${API_BASE}/api/clips/finished/${clipId}/srt`;
}
