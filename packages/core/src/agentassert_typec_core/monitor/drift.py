from __future__ import annotations

import math
from collections import defaultdict, deque
from typing import Any

from agentassert_typec_core.models.session import DriftReport


class DriftTracker:
    def __init__(self, window: int = 50) -> None:
        self._window = window
        self._current_counts: dict[str, int] = defaultdict(int)
        self._baseline_counts: dict[str, int] | None = None
        self._call_sequence: deque[str] = deque(maxlen=window)
        self._total_updates = 0
        self._violation_count = 0

    def update(self, tool: str, state: dict[str, Any] | None = None) -> None:
        if state is None:
            state = {}
        if len(self._call_sequence) == self._window:
            evicted = self._call_sequence[0]
            self._current_counts[evicted] -= 1
        self._call_sequence.append(tool)
        self._current_counts[tool] += 1
        self._total_updates += 1

        if self._total_updates == self._window and self._baseline_counts is None:
            self._baseline_counts = dict(self._current_counts)

    def current_jsd(self) -> float:
        if self._baseline_counts is None or self._total_updates < self._window:
            return 0.0
        return self._compute_jsd(self._baseline_counts, dict(self._current_counts))

    def _compute_jsd(self, p_counts: dict[str, int], q_counts: dict[str, int]) -> float:
        keys = set(p_counts) | set(q_counts)
        total_p = max(sum(p_counts.values()), 1)
        total_q = max(sum(q_counts.values()), 1)

        p = {k: p_counts.get(k, 0) / total_p for k in keys}
        q = {k: q_counts.get(k, 0) / total_q for k in keys}
        m = {k: 0.5 * (p[k] + q[k]) for k in keys}

        def kl(a: dict[str, float], b: dict[str, float]) -> float:
            return sum(
                a[k] * math.log(a[k] / b[k])
                for k in a if a[k] > 0 and b[k] > 0
            )

        jsd = 0.5 * kl(p, m) + 0.5 * kl(q, m)
        return min(jsd, 1.0)

    def report(self) -> DriftReport:
        total = max(sum(self._current_counts.values()), 1)
        return DriftReport(
            current_jsd=self.current_jsd(),
            tool_distribution={k: v / total for k, v in self._current_counts.items()},
            window_size=self._window,
            violation_count=self._violation_count,
        )
