const API_BASE = "/api"

export interface ScanRequest {
  url: string
  clip_count: number
  duration_target: string
  content_type?: string
  subtitle_lang: string
  layout: string
}

export interface ScanResponse {
  job_id: string
  video_id: string
}

export interface ClipInfo {
  id: string
  video_id: string
  clip_index: number
  start_time: number
  end_time: number
  duration: number
  hook_title: string
  score: number
  caption: string
  hashtags: string[]
  content_type: string
  layout: string
  subtitle_lang?: string
  status: string
  error_msg: string | null
  file_path: string | null
  transcript?: string | null
  subtitles_json?: string | null
}

export interface VideoInfo {
  id: string
  url: string
  title: string
  duration: number
  thumbnail: string
  channel: string
  status: string
  clips: ClipInfo[]
}

export interface Project {
  id: string
  url: string
  title: string
  duration: number
  thumbnail: string
  clip_count: number
  status: string
  created_at: string
}

export async function startScan(req: ScanRequest): Promise<ScanResponse> {
  const res = await fetch(`${API_BASE}/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Gagal memulai scan" }))
    throw new Error(err.detail || "Gagal memulai scan")
  }
  return res.json()
}

export async function getVideo(videoId: string): Promise<VideoInfo> {
  const res = await fetch(`${API_BASE}/videos/${videoId}`)
  if (!res.ok) throw new Error("Video tidak ditemukan")
  return res.json()
}

export async function getProjects(): Promise<Project[]> {
  const res = await fetch(`${API_BASE}/projects`)
  if (!res.ok) return []
  return res.json()
}

export interface RescanParams {
  clip_count?: number
  duration_target?: string
  content_type?: string
  subtitle_lang?: string
  layout?: string
}

export interface SubtitleCue {
  start: number
  end: number
  text: string
}

export interface ClipSubtitlesResponse {
  clip_id: string
  subtitle_lang: string
  transcript: string
  cues: SubtitleCue[]
}

export interface EditClipParams {
  layout?: string
  subtitle_lang?: string
  start_time?: number
  end_time?: number
  hook_title?: string
  custom_subtitles?: SubtitleCue[]
  custom_transcript?: string
}

export async function getClipSubtitles(clipId: string): Promise<ClipSubtitlesResponse> {
  const res = await fetch(`${API_BASE}/clips/${clipId}/subtitles`)
  if (!res.ok) throw new Error("Gagal mengambil transkrip subtitle")
  return res.json()
}

export async function deleteProject(videoId: string): Promise<{ deleted: string }> {
  const res = await fetch(`${API_BASE}/videos/${videoId}`, {
    method: "DELETE",
  })
  if (!res.ok) throw new Error("Gagal menghapus proyek")
  return res.json()
}

export async function rescanVideo(videoId: string, params: RescanParams): Promise<{ job_id: string; video_id: string }> {
  const res = await fetch(`${API_BASE}/videos/${videoId}/rescan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || "Gagal rescan video")
  }
  return res.json()
}

export async function retryClip(
  clipId: string,
  params: string | EditClipParams
): Promise<{ job_id: string; clip_id: string }> {
  const body = typeof params === "string" ? { layout: params } : params
  const res = await fetch(`${API_BASE}/clips/${clipId}/retry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error("Gagal render ulang klip")
  return res.json()
}

export function downloadClipUrl(clipId: string): string {
  return `${API_BASE}/clips/${clipId}/download`
}

export function previewClipUrl(clipId: string): string {
  return `${API_BASE}/clips/${clipId}/preview`
}

export interface JobInfo {
  id: string
  video_id: string
  clip_id?: string
  job_type: string
  status: "pending" | "running" | "done" | "error"
  phase?: string
  progress?: number
  message?: string
  error_msg?: string
}

export async function getJob(jobId: string): Promise<JobInfo> {
  const res = await fetch(`${API_BASE}/jobs/${jobId}`)
  if (!res.ok) throw new Error("Gagal mengambil status job")
  return res.json()
}

export function streamJob(jobId: string, onEvent: (e: Record<string, unknown>) => void): EventSource {
  const es = new EventSource(`${API_BASE}/jobs/${jobId}/stream`)
  es.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data)
      if (data.event !== "ping") onEvent(data)
    } catch (_) {}
  }
  // Let EventSource auto-reconnect on transient error; do not terminate stream prematurely
  return es
}
