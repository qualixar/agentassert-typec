from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from agentassert_typec_core.models.session import SessionContext, HistoryDigest, DriftReport


@dataclass(frozen=True, kw_only=True)
class TypeCEvent:
    session_id: str
    contract_id: str
    timestamp: float = field(default_factory=time.monotonic)


@dataclass(frozen=True, kw_only=True)
class PreAction(TypeCEvent):
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    context: SessionContext | None = None


@dataclass(frozen=True, kw_only=True)
class PostAction(TypeCEvent):
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    result: Any = None
    state: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class TurnStart(TypeCEvent):
    user_input: str
    history_summary: HistoryDigest | None = None


@dataclass(frozen=True, kw_only=True)
class TurnEnd(TypeCEvent):
    assistant_output: str
    state_delta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class SessionStart(TypeCEvent):
    workdir: str
    model: str
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class SessionEnd(TypeCEvent):
    theta: float
    drift_report: DriftReport | None = None


@dataclass(frozen=True, kw_only=True)
class ContextWindow(TypeCEvent):
    token_count: int
    prefix_hash: str
