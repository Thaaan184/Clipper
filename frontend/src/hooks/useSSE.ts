import { useState, useEffect, useRef } from "react"
import { streamJob, getJob } from "@/lib/api"

export interface ProgressEvent {
  event: string
  job_id: string
  phase?: string
  progress?: number
  message?: string
  clips?: unknown[]
  error?: string
  clip_id?: string
  video_id?: string
}

export function useSSE(jobId: string | null) {
  const [events, setEvents] = useState<ProgressEvent[]>([])
  const [latest, setLatest] = useState<ProgressEvent | null>(null)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    if (!jobId) return

    setEvents([])
    setLatest(null)
    setDone(false)
    setError(null)

    let isDone = false

    const handleEvent = (evt: ProgressEvent) => {
      setLatest(evt)
      setEvents((prev) => {
        if (
          prev.length > 0 &&
          prev[prev.length - 1].message === evt.message &&
          prev[prev.length - 1].progress === evt.progress
        ) {
          return prev
        }
        return [...prev, evt]
      })

      if (evt.event === "done") {
        isDone = true
        setDone(true)
      }
      if (evt.event === "error") {
        isDone = true
        setError(evt.error || "Error tidak diketahui")
        setDone(true)
      }
    }

    // 1. SSE stream
    const es = streamJob(jobId, (ev) => {
      handleEvent(ev as unknown as ProgressEvent)
    })

    // 2. Fallback polling every 2s
    const poll = async () => {
      if (isDone) return
      try {
        const job = await getJob(jobId)
        if (isDone) return

        if (job.status === "done") {
          handleEvent({
            event: "done",
            job_id: jobId,
            progress: 100,
            message: job.message || "Selesai",
            video_id: job.video_id,
          })
        } else if (job.status === "error") {
          handleEvent({
            event: "error",
            job_id: jobId,
            error: job.error_msg || "Proses gagal",
          })
        } else if (job.status === "running" || job.status === "pending") {
          handleEvent({
            event: "progress",
            job_id: jobId,
            phase: job.phase,
            progress: job.progress,
            message: job.message || "Memproses...",
          })
        }
      } catch (_) {}
    }

    pollTimerRef.current = setInterval(poll, 2000)
    poll()

    return () => {
      es.close()
      if (pollTimerRef.current) clearInterval(pollTimerRef.current)
    }
  }, [jobId])

  return { events, latest, done, error }
}
