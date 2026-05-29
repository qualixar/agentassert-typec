from __future__ import annotations

"""Serializers for SessionMonitor sub-systems → SessionStore.

Rules:
- Adapt to actual attribute names in the source, not LLD names.
- _seen_tools_turn is NOT persisted (per-turn, resets on every turn).
- ThetaScorer: serialize raw list fields (no _score/_penalty_count).
- ViolationLog: _log is a deque[dict] — serialize directly.
"""

import logging
from collections import defaultdict, deque
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agentassert_typec_core.monitor.drift import DriftTracker
    from agentassert_typec_core.monitor.session import SessionMonitor
    from agentassert_typec_core.monitor.theta import ThetaScorer
    from agentassert_typec_core.monitor.violation_log import ViolationLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# ThetaScorer
# ---------------------------------------------------------------------------

def dump_theta(theta: "ThetaScorer") -> dict[str, Any]:
    return {
        "compliance_scores": list(theta._compliance_scores),
        "drift_scores": list(theta._drift_scores),
        "violation_count": theta._violation_count,
        "recovery_attempts": theta._recovery_attempts,
        "recovery_successes": theta._recovery_successes,
        "penalty_sum": theta._penalty_sum,
    }


def load_theta(theta: "ThetaScorer", data: dict[str, Any]) -> None:
    try:
        theta._compliance_scores = list(data.get("compliance_scores", []))
        theta._drift_scores = list(data.get("drift_scores", []))
        theta._violation_count = int(data.get("violation_count", 0))
        theta._recovery_attempts = int(data.get("recovery_attempts", 0))
        theta._recovery_successes = int(data.get("recovery_successes", 0))
        penalty_sum = float(data.get("penalty_sum", 0.0))
        # Guard against corrupted values
        if not (0.0 <= penalty_sum <= 10.0):
            logger.warning("Loaded penalty_sum %s is out of range, clamping", penalty_sum)
            penalty_sum = max(0.0, min(10.0, penalty_sum))
        theta._penalty_sum = penalty_sum
    except Exception as exc:
        logger.warning("load_theta failed: %s — using fresh state", exc)


# ---------------------------------------------------------------------------
# DriftTracker
# ---------------------------------------------------------------------------

def dump_drift(drift: "DriftTracker") -> dict[str, Any]:
    return {
        "call_sequence": list(drift._call_sequence),
        "baseline_counts": dict(drift._baseline_counts) if drift._baseline_counts is not None else None,
        "current_counts": dict(drift._current_counts),
        "total_updates": drift._total_updates,
    }


def load_drift(drift: "DriftTracker", data: dict[str, Any]) -> None:
    try:
        drift._call_sequence = deque(data.get("call_sequence", []), maxlen=drift._window)
        baseline = data.get("baseline_counts")
        drift._baseline_counts = dict(baseline) if baseline is not None else None
        drift._current_counts = defaultdict(int, data.get("current_counts", {}))
        drift._total_updates = int(data.get("total_updates", 0))
    except Exception as exc:
        logger.warning("load_drift failed: %s — using fresh state", exc)


# ---------------------------------------------------------------------------
# ViolationLog
# ---------------------------------------------------------------------------

def dump_violations(log: "ViolationLog") -> list[dict[str, Any]]:
    # _log is deque[dict] — dump the last 10 000 entries to prevent unbounded growth
    entries = list(log._log)
    if len(entries) > 10_000:
        entries = entries[-10_000:]
    return entries


def load_violations(log: "ViolationLog", data: list[dict[str, Any]]) -> None:
    try:
        for entry in data:
            if isinstance(entry, dict):
                log._log.append(entry)
    except Exception as exc:
        logger.warning("load_violations failed: %s — using empty log", exc)


# ---------------------------------------------------------------------------
# SessionMonitor meta
# ---------------------------------------------------------------------------

def dump_meta(monitor: "SessionMonitor") -> dict[str, Any]:
    return {
        "turn_count": monitor._turn_count,
        "deny_count": monitor._deny_count,
        "seen_tools_session": sorted(monitor._seen_tools_session),
    }


def load_meta(monitor: "SessionMonitor", data: dict[str, Any]) -> None:
    try:
        monitor._turn_count = int(data.get("turn_count", 0))
        monitor._deny_count = int(data.get("deny_count", 0))
        monitor._seen_tools_session = set(data.get("seen_tools_session", []))
        # _seen_tools_turn is NOT restored — per-turn state
    except Exception as exc:
        logger.warning("load_meta failed: %s — using fresh state", exc)


# ---------------------------------------------------------------------------
# Phase 3: Cost state
# ---------------------------------------------------------------------------

def dump_cost(monitor: "SessionMonitor") -> dict[str, Any]:
    return {
        "accumulated_usd": monitor._accumulated_cost_usd,
    }


def load_cost(monitor: "SessionMonitor", data: dict[str, Any]) -> None:
    try:
        monitor._accumulated_cost_usd = float(data.get("accumulated_usd", 0.0))
    except Exception as exc:
        logger.warning("load_cost failed: %s — using 0.0", exc)


# ---------------------------------------------------------------------------
# Phase 3: Repetition guard state
# ---------------------------------------------------------------------------

def dump_repetition(monitor: "SessionMonitor") -> dict[str, Any]:
    return {
        "history": list(monitor._tool_call_history),
        "hash_counts": dict(monitor._sequence_hash_counts),
    }


def load_repetition(monitor: "SessionMonitor", data: dict[str, Any]) -> None:
    try:
        history = data.get("history", [])
        monitor._tool_call_history = deque(history, maxlen=1000)
        monitor._sequence_hash_counts = defaultdict(int, data.get("hash_counts", {}))
    except Exception as exc:
        logger.warning("load_repetition failed: %s — using fresh state", exc)
