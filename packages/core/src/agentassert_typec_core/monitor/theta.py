from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ThetaScorer:
    weights: object = None

    _compliance_scores: list[float] = field(default_factory=list)
    _drift_scores: list[float] = field(default_factory=list)
    _violation_count: int = 0
    _recovery_attempts: int = 0
    _recovery_successes: int = 0
    _penalty_sum: float = 0.0

    def record_compliance(self, c_hard: float, c_soft: float) -> None:
        self._compliance_scores.append(0.7 * c_hard + 0.3 * c_soft)

    def record_drift(self, jsd: float) -> None:
        self._drift_scores.append(jsd)

    def record_violation(self) -> None:
        self._violation_count += 1

    def record_recovery(self, success: bool) -> None:
        self._recovery_attempts += 1
        if success:
            self._recovery_successes += 1

    def apply_penalty(self, delta: float) -> None:
        self._penalty_sum += delta

    def record_action(self, tool: str) -> None:
        pass

    def compute(self) -> float:
        w_c = 0.35
        w_d = 0.25
        w_e = 0.20
        w_s = 0.20

        if self.weights:
            w_c = getattr(self.weights, "compliance", 0.35)
            w_d = getattr(self.weights, "drift", 0.25)
            w_e = getattr(self.weights, "event_freq", 0.20)
            w_s = getattr(self.weights, "recovery_success", 0.20)

        c_bar = (
            sum(self._compliance_scores) / len(self._compliance_scores)
            if self._compliance_scores
            else 1.0
        )
        d_bar = (
            sum(self._drift_scores) / len(self._drift_scores)
            if self._drift_scores
            else 0.0
        )
        e_term = 1.0 / (1.0 + self._violation_count)
        s_term = (
            self._recovery_successes / self._recovery_attempts
            if self._recovery_attempts > 0
            else 1.0
        )

        theta = w_c * c_bar + w_d * (1.0 - d_bar) + w_e * e_term + w_s * s_term
        return max(0.0, min(1.0, theta - self._penalty_sum))
