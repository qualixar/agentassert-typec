from __future__ import annotations

import hashlib
import threading
import time
from pathlib import Path

from agentassert_typec_core.monitor.session import SessionMonitor


class ContractWatcher:
    def __init__(self, contract_path: str, interval: float = 0.5) -> None:
        self._path = Path(contract_path)
        self._interval = interval
        self._current: SessionMonitor | None = None
        self._pending: SessionMonitor | None = None
        self._lock = threading.RLock()
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def set_monitor(self, monitor: SessionMonitor) -> None:
        with self._lock:
            self._current = monitor

    def swap_if_pending(self) -> SessionMonitor | None:
        with self._lock:
            if self._pending is not None:
                self._current, self._pending = self._pending, None
                return self._current
            return None

    def _watch_loop(self) -> None:
        try:
            last_hash = self._file_hash()
        except Exception:
            last_hash = ""

        while self._running:
            time.sleep(self._interval)
            try:
                current_hash = self._file_hash()
                if current_hash != last_hash:
                    last_hash = current_hash
                    self._try_reload()
            except Exception:
                pass

    def _try_reload(self) -> None:
        try:
            new_monitor = SessionMonitor.from_yaml(str(self._path))
            with self._lock:
                self._pending = new_monitor
        except Exception:
            pass

    def _file_hash(self) -> str:
        content = self._path.read_bytes()
        return hashlib.sha256(content).hexdigest()
