"""SSE Event bus with database persistence and Last-Event-ID replay support."""

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from clipforge.jobs.models import JobEvent


class EventBroadcaster:
    """Manages active SSE subscriber queues per job."""

    def __init__(self) -> None:
        self._listeners: dict[str, set[asyncio.Queue[JobEvent]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, job_id: str) -> asyncio.Queue[JobEvent]:
        async with self._lock:
            if job_id not in self._listeners:
                self._listeners[job_id] = set()
            queue: asyncio.Queue[JobEvent] = asyncio.Queue()
            self._listeners[job_id].add(queue)
            return queue

    async def unsubscribe(self, job_id: str, queue: asyncio.Queue[JobEvent]) -> None:
        async with self._lock:
            if job_id in self._listeners:
                self._listeners[job_id].discard(queue)
                if not self._listeners[job_id]:
                    del self._listeners[job_id]

    async def publish(
        self,
        db: aiosqlite.Connection,
        job_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> JobEvent:
        """Persist event to database and push to all active in-memory listeners."""
        now_iso = datetime.now(UTC).isoformat()
        payload_json = json.dumps(payload)

        cursor = await db.execute(
            "INSERT INTO events (job_id, ts, type, payload_json) VALUES (?, ?, ?, ?)",
            (job_id, now_iso, event_type, payload_json),
        )
        await db.commit()
        event_id = cursor.lastrowid

        event = JobEvent(
            id=event_id,
            job_id=job_id,
            ts=now_iso,
            type=event_type,
            payload=payload,
        )

        async with self._lock:
            listeners = list(self._listeners.get(job_id, set()))

        for q in listeners:
            await q.put(event)

        return event

    async def replay_events_since(
        self,
        db: aiosqlite.Connection,
        job_id: str,
        last_event_id: int,
    ) -> list[JobEvent]:
        """Fetch historical events strictly after last_event_id for reconnection replay."""
        async with db.execute(
            "SELECT id, ts, type, payload_json FROM events WHERE job_id = ? AND id > ? ORDER BY id ASC",
            (job_id, last_event_id),
        ) as cursor:
            rows = await cursor.fetchall()
            return [
                JobEvent(
                    id=row[0],
                    job_id=job_id,
                    ts=row[1],
                    type=row[2],
                    payload=json.loads(row[3]),
                )
                for row in rows
            ]


broadcaster = EventBroadcaster()
