"""Durable run events and long-term memory backed by SQLite (stdlib only)."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from typing import Any

_TOKEN = re.compile(r"[a-z0-9_]{3,}")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower()))


class Store:
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.RLock()
        with self._lock:
            self._db.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, ts REAL, kind TEXT, data TEXT);
                CREATE INDEX IF NOT EXISTS events_run ON events(run_id);
                CREATE TABLE IF NOT EXISTS memory(
                    key TEXT PRIMARY KEY, value TEXT, importance REAL, created REAL,
                    expires REAL, hits INTEGER DEFAULT 0);
                """
            )

    def log(self, run_id: str, kind: str, data: Any) -> None:
        with self._lock, self._db:
            self._db.execute(
                "INSERT INTO events(run_id, ts, kind, data) VALUES (?,?,?,?)",
                (run_id, time.time(), kind, json.dumps(data, default=str)),
            )

    def events(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT ts, kind, data FROM events WHERE run_id=? ORDER BY id", (run_id,)
            ).fetchall()
        return [{"ts": ts, "kind": kind, "data": json.loads(data)} for ts, kind, data in rows]

    def remember(self, key: str, value: str, *, importance: float = 0.5, ttl: float | None = None) -> None:
        now = time.time()
        with self._lock, self._db:
            self._db.execute(
                "INSERT OR REPLACE INTO memory(key, value, importance, created, expires, hits) "
                "VALUES (?,?,?,?,?,COALESCE((SELECT hits FROM memory WHERE key=?),0))",
                (key, value, importance, now, None if ttl is None else now + ttl, key),
            )

    def recall(self, key: str) -> str | None:
        with self._lock:
            row = self._db.execute(
                "SELECT value FROM memory WHERE key=? AND (expires IS NULL OR expires>?)", (key, time.time())
            ).fetchone()
        return row[0] if row else None

    def search(self, query: str, limit: int = 3) -> list[tuple[str, str]]:
        """Rank live memories by token overlap, importance, usefulness and recency."""
        q = _tokens(query)
        if not q:
            return []
        now = time.time()
        with self._lock:
            rows = self._db.execute(
                "SELECT key, value, importance, created, hits FROM memory WHERE expires IS NULL OR expires>?",
                (now,),
            ).fetchall()
        scored = []
        for key, value, importance, created, hits in rows:
            overlap = len(q & _tokens(value)) / len(q)
            if overlap == 0:
                continue
            age_days = (now - created) / 86400
            score = overlap * (0.5 + importance) * (1 + min(hits, 10) * 0.05) / (1 + age_days / 30)
            scored.append((score, key, value))
        scored.sort(reverse=True)
        top = scored[:limit]
        if top:
            with self._lock, self._db:
                self._db.executemany("UPDATE memory SET hits=hits+1 WHERE key=?", [(k,) for _, k, _ in top])
        return [(k, v) for _, k, v in top]

    def sweep(self, max_entries: int = 10_000) -> int:
        """Drop expired entries, then the least valuable ones beyond max_entries."""
        with self._lock, self._db:
            n = self._db.execute("DELETE FROM memory WHERE expires IS NOT NULL AND expires<=?", (time.time(),)).rowcount
            n += self._db.execute(
                "DELETE FROM memory WHERE key IN (SELECT key FROM memory ORDER BY importance + hits*0.05 DESC, "
                "created DESC LIMIT -1 OFFSET ?)",
                (max_entries,),
            ).rowcount
        return n
