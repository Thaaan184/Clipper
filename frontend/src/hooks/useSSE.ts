import { useState, useEffect } from "react"
import { streamJob } from "@/lib/api"

export interface ProgressEvent {
  event: string
  job_id: string
  phase?: string
  progress?: number
  message?: string
  clips?: unknown[]
  error?: string
  clip_id?: string
}

export function useSSE(jobId: string | null) {
  const [events, setEvents] = useState<ProgressEvent[]>([])
  const [latest, setLatest] = useState<ProgressEvent | null>(null)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!jobId) return

    setEvents([])
    setLatest(null)
    setDone(false)
    setError(null)

    const es = streamJob(jobId, (ev) => {
      const evt = ev as unknown as ProgressEvent
      setLatest(evt)
      setEvents((prev) => [...prev, evt])

      if (evt.event === "done") setDone(true)
      if (evt.event === "error") {
        setError(evt.error || "Error tidak diketahui")
        setDone(true)
      }
    })

    return () => es.close()
  }, [jobId])

  return { events, latest, done, error }
}
