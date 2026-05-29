from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS session_state (
    key        TEXT PRIMARY KEY NOT NULL,
    value      TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_key ON session_state(key);
"""


class SessionStore:
    """SQLite-backed key-value store for session state.

    Thread-safe. Uses WAL mode. Write-behind with 5 s debounce.
    Gracefully degrades (disabled) on disk-full errors — session continues.
    """

    def __init__(self, db_path: str) -> None:
        self._path = db_path
        self._conn: sqlite3.Connection | None = None
        self._dirty: bool = False
        self._pending: dict[str, Any] = {}
        self._lock = threading.RLock()
        self._flush_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._disabled: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def open(self) -> None:
        """Open DB, create schema, start background flush thread."""
        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
        with self._lock:
            self._conn = sqlite3.connect(
                self._path,
                check_same_thread=False,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

        self._stop_event.clear()
        self._flush_thread = threading.Thread(
            target=self._flush_loop,
            args=(5.0,),
            daemon=True,
            name="agentassert-store-flush",
        )
        self._flush_thread.start()

    def close(self) -> None:
        """Stop flush thread, do a final synchronous flush, close connection."""
        self._stop_event.set()
        if self._flush_thread is not None:
            self._flush_thread.join(timeout=10)
            self._flush_thread = None
        self.flush()
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any | None:
        """Load and deserialize a value. Returns None if key absent."""
        if self._disabled or self._conn is None:
            return None
        with self._lock:
            try:
                cur = self._conn.execute(
                    "SELECT value FROM session_state WHERE key = ?", (key,)
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return json.loads(row[0])
            except Exception as exc:
                logger.warning("SessionStore.get(%s) failed: %s", key, exc)
                return None

    def put(self, key: str, value: Any) -> None:
        """Mark key dirty. Does NOT write to DB immediately (write-behind)."""
        if self._disabled:
            return
        with self._lock:
            self._pending[key] = value
            self._dirty = True

    def flush(self) -> None:
        """Write all dirty keys to DB atomically. Called by flush thread and close()."""
        if self._disabled or self._conn is None:
            return
        with self._lock:
            if not self._dirty:
                return
            snapshot = dict(self._pending)
            self._dirty = False

        try:
            now = time.time()
            with self._lock:
                for key, value in snapshot.items():
                    self._conn.execute(
                        "INSERT OR REPLACE INTO session_state (key, value, updated_at) "
                        "VALUES (?, ?, ?)",
                        (key, json.dumps(value), now),
                    )
                self._conn.commit()
        except sqlite3.OperationalError as exc:
            logger.warning(
                "SessionStore.flush() failed (disk full?): %s — disabling persistence", exc
            )
            self._disabled = True
        except Exception as exc:
            logger.warning("SessionStore.flush() unexpected error: %s", exc)

    def is_dirty(self) -> bool:
        with self._lock:
            return self._dirty

    # ------------------------------------------------------------------
    # Background flush loop
    # ------------------------------------------------------------------

    def _flush_loop(self, interval: float = 5.0) -> None:
        while not self._stop_event.wait(timeout=interval):
            self.flush()
