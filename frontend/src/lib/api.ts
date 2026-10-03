const API_BASE = "/api"

export interface ScanRequest {
  url: string
  clip_count: number
  duration_target: string
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
  status: string
  error_msg: string | null
  file_path: string | null
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

export async function retryClip(clipId: string, layout: string): Promise<{ job_id: string }> {
  const res = await fetch(`${API_BASE}/clips/${clipId}/retry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ layout }),
  })
  if (!res.ok) throw new Error("Gagal retry clip")
  return res.json()
}

export function downloadClipUrl(clipId: string): string {
  return `${API_BASE}/clips/${clipId}/download`
}

export function streamJob(jobId: string, onEvent: (e: Record<string, unknown>) => void): EventSource {
  const es = new EventSource(`${API_BASE}/jobs/${jobId}/stream`)
  es.onmessage = (ev) => {
    try {
      const data = JSON.parse(ev.data)
      if (data.event !== "ping") onEvent(data)
    } catch (_) {}
  }
  es.onerror = () => {
    onEvent({ event: "error", error: "Koneksi SSE terputus" })
    es.close()
  }
  return es
}
