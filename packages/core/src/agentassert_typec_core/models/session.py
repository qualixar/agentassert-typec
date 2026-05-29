from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SessionContext:
    session_id: str
    stated_fields: frozenset[str] = field(default_factory=frozenset)
    turn_index: int = 0
    token_count: int = 0

    def has_stated_field(self, field: str) -> bool:
        return field in self.stated_fields


@dataclass
class HistoryDigest:
    turn_count: int = 0
    total_tokens: int = 0
    role_pattern: str = ""


@dataclass
class DriftReport:
    current_jsd: float = 0.0
    tool_distribution: dict[str, float] = field(default_factory=dict)
    window_size: int = 0
    violation_count: int = 0
