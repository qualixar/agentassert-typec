from __future__ import annotations

import threading
from collections import deque
from typing import Any


class ViolationLog:
    def __init__(self, maxlen: int = 1000) -> None:
        self._log: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def record(self, name: str, event_type: str, tool: str, reason: str) -> None:
        with self._lock:
            self._log.append({
                "name": name,
                "event_type": event_type,
                "tool": tool,
                "reason": reason,
                "kind": "hard",
            })

    def record_soft(self, name: str, event_type: str, tool: str, reason: str) -> None:
        with self._lock:
            self._log.append({
                "name": name,
                "event_type": event_type,
                "tool": tool,
                "reason": reason,
                "kind": "soft",
            })

    def all_violations(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._log)
