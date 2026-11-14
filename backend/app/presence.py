"""Who is looking at a document right now.

Deliberately in-memory: presence is ephemeral, losing it on restart is harmless, and the
app runs as a single instance. Clients heartbeat every few seconds; entries expire after
`ttl_seconds`. A multi-instance deployment would move this to Redis (same interface).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(slots=True)
class _Entry:
    name: str
    email: str
    editing: bool
    last_seen: float


class PresenceTracker:
    def __init__(self, ttl_seconds: float = 15.0, clock: Callable[[], float] = time.monotonic) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._docs: dict[str, dict[int, _Entry]] = {}

    def _prune(self, now: float) -> None:
        for doc_id in list(self._docs):
            users = self._docs[doc_id]
            for uid in [u for u, e in users.items() if now - e.last_seen > self._ttl]:
                del users[uid]
            if not users:
                del self._docs[doc_id]

    def heartbeat(self, doc_id: str, *, user_id: int, name: str, email: str, editing: bool) -> list[dict]:
        """Record that `user_id` is present and return everyone *else* who is."""
        now = self._clock()
        with self._lock:
            self._prune(now)
            users = self._docs.setdefault(doc_id, {})
            users[user_id] = _Entry(name=name, email=email, editing=editing, last_seen=now)
            return [
                {"id": uid, "name": e.name, "email": e.email, "editing": e.editing}
                for uid, e in sorted(users.items())
                if uid != user_id
            ]

    def leave(self, doc_id: str, user_id: int) -> None:
        with self._lock:
            users = self._docs.get(doc_id)
            if users:
                users.pop(user_id, None)
                if not users:
                    del self._docs[doc_id]
