from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TypeCDecision(Enum):
    ALLOW = "allow"
    MODIFY = "modify"
    DENY = "deny"


@dataclass(frozen=True)
class DecisionResult:
    decision: TypeCDecision
    reason: str = ""
    modified_args: dict[str, Any] | None = None
    violation_name: str = ""
    theta_penalty: float = 0.0

    def is_deny(self) -> bool:
        return self.decision == TypeCDecision.DENY

    def is_modify(self) -> bool:
        return self.decision == TypeCDecision.MODIFY
