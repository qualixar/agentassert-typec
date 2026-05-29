from __future__ import annotations

"""Phase 3 content evaluators: pii_filter, cost_ceiling, repetition_guard.

All functions return DecisionResult | None.
None means "allow / no action needed".
"""

import hashlib
import json
import logging
from collections import deque
from typing import TYPE_CHECKING, Any

from agentassert_typec_core.models.decisions import DecisionResult, TypeCDecision

if TYPE_CHECKING:
    from agentassert_typec_core.dsl.ast_compiler import CompiledContract
    from agentassert_typec_core.models.events import PreAction
    from agentassert_typec_core.monitor.session import SessionMonitor
    from agentassert_typec_core.monitor.violation_log import ViolationLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default provider prices (USD per million tokens): input, output
# ---------------------------------------------------------------------------
_DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    "anthropic":  (3.00,  15.00),
    "openai":     (2.50,  10.00),
    "openrouter": (0.50,   2.00),
    "gemini":     (0.075,  0.30),
}


# ===========================================================================
# pii_filter
# ===========================================================================

def evaluate_pii_filter(
    text: str,
    compiled: "CompiledContract",
    violations: "ViolationLog",
    is_streaming: bool,
) -> DecisionResult | None:
    if compiled.pii_filter_config is None:
        return None
    if not text:
        return None

    config = compiled.pii_filter_config
    action = config.streaming_action if is_streaming else config.action

    found: list[tuple[str, str]] = []
    for (name, pattern) in compiled.pii_compiled_patterns:
        matches = pattern.findall(text)
        for match in matches:
            found.append((name, str(match)[:50]))

    if not found:
        return None

    reason = f"PII detected: {', '.join(sorted(set(f[0] for f in found)))}"

    if action in ("log", "warn"):
        violations.record_soft("pii_filter", "PostAction", "response", reason)
        return None

    elif action == "redact":
        violations.record_soft("pii_filter", "PostAction", "response", reason)
        return DecisionResult(
            decision=TypeCDecision.REDACT,
            reason=reason,
            violation_name="pii_filter",
        )

    elif action == "block":
        if is_streaming:
            # Cannot block already-yielded streaming content — degrade to warn
            violations.record_soft(
                "pii_filter", "PostAction", "response", f"[stream] {reason}"
            )
            return None
        violations.record("pii_filter", "PostAction", "response", reason)
        return DecisionResult(
            decision=TypeCDecision.DENY,
            reason=f"ContractBreach: pii_filter — {reason}",
            violation_name="pii_filter",
        )

    return None


def _apply_pii_redaction(
    text: str,
    patterns: list[tuple[str, Any]],
) -> str:
    result = text
    for (name, pattern) in patterns:
        result = pattern.sub(f"[REDACTED:{name.upper()}]", result)
    return result


# ===========================================================================
# cost_ceiling
# ===========================================================================

def evaluate_cost_ceiling(
    event: "PreAction",
    compiled: "CompiledContract",
    accumulated_cost: float,
    violations: "ViolationLog",
) -> DecisionResult | None:
    if compiled.cost_ceiling_config is None:
        return None

    config = compiled.cost_ceiling_config
    if accumulated_cost < config.max_usd_per_session:
        return None

    reason = (
        f"Cost ceiling breached: ${accumulated_cost:.4f} >= "
        f"${config.max_usd_per_session:.2f}"
    )

    if config.action_on_breach == "deny":
        violations.record("cost_ceiling", "PreAction", event.tool, reason)
        return DecisionResult(
            decision=TypeCDecision.DENY,
            reason=reason,
            violation_name="cost_ceiling",
        )
    elif config.action_on_breach == "warn":
        violations.record_soft("cost_ceiling", "PreAction", event.tool, reason)
        return None
    else:  # log
        return None


def _extract_usage(resp_data: dict, provider: str) -> tuple[int, int] | None:
    """Extract (input_tokens, output_tokens) from provider-specific response."""
    if not isinstance(resp_data, dict):
        return None

    if provider == "anthropic":
        usage = resp_data.get("usage", {})
        inp = usage.get("input_tokens")
        out = usage.get("output_tokens")
        if inp is not None and out is not None:
            return (int(inp), int(out))

    elif provider in ("openai", "openrouter"):
        usage = resp_data.get("usage", {})
        inp = usage.get("prompt_tokens")
        out = usage.get("completion_tokens")
        if inp is not None and out is not None:
            return (int(inp), int(out))

    elif provider == "gemini":
        meta = resp_data.get("usageMetadata", {})
        inp = meta.get("promptTokenCount")
        out = meta.get("candidatesTokenCount")
        if inp is not None and out is not None:
            return (int(inp), int(out))

    return None


def _parse_streaming_usage(text: str) -> dict | None:
    """Scan SSE lines from the end for last data: line containing usage info."""
    lines = text.splitlines()
    for line in reversed(lines):
        if not line.startswith("data: "):
            continue
        try:
            payload = json.loads(line[6:])
            if "usage" in payload or "usageMetadata" in payload:
                return payload
        except json.JSONDecodeError:
            continue
    return None


def _update_cost(
    resp_data: dict,
    canonical: Any,  # CanonicalRequest
    monitor: "SessionMonitor",
) -> None:
    """Parse usage from response, compute cost, accumulate on monitor."""
    if monitor._compiled.cost_ceiling_config is None:
        return

    usage = _extract_usage(resp_data, canonical.provider)
    if usage is None:
        return

    input_tokens, output_tokens = usage
    config = monitor._compiled.cost_ceiling_config
    provider = canonical.provider

    # Price resolution: contract.provider_price_map > contract.global_price > default
    if provider in config.provider_price_map:
        price_in = config.provider_price_map[provider].input
        price_out = config.provider_price_map[provider].output
    elif config.price_per_million_input is not None:
        price_in = config.price_per_million_input
        price_out = config.price_per_million_output or config.price_per_million_input
    else:
        price_in, price_out = _DEFAULT_PRICES.get(provider, (1.0, 5.0))

    cost = (input_tokens * price_in + output_tokens * price_out) / 1_000_000

    with monitor._cost_lock:
        monitor._accumulated_cost_usd += cost

    # Mark store dirty for persistence
    if monitor._store is not None:
        monitor._store.put("cost", {"accumulated_usd": monitor._accumulated_cost_usd})


# ===========================================================================
# repetition_guard
# ===========================================================================

def evaluate_repetition_guard(
    event: "PreAction",
    compiled: "CompiledContract",
    tool_history: deque,
    seq_hash_counts: dict,
    violations: "ViolationLog",
) -> DecisionResult | None:
    if compiled.repetition_guard_config is None:
        return None

    config = compiled.repetition_guard_config
    tool = event.tool

    # Skip ignored tools
    for pattern in compiled.repetition_guard_ignore_patterns:
        if pattern.search(tool):
            return None

    # Build candidate history (don't mutate the actual deque — caller commits on allow)
    candidate_history = list(tool_history) + [tool]

    W = config.window_size
    if len(candidate_history) < W:
        return None

    window = tuple(candidate_history[-W:])
    seq_key = hashlib.md5("|".join(window).encode()).hexdigest()

    current_count = seq_hash_counts.get(seq_key, 0) + 1  # +1 for this potential call

    if current_count > config.max_repeats:
        reason = (
            f"Repetition detected: [{' → '.join(window)}] "
            f"seen {current_count} times (max {config.max_repeats})"
        )
        if config.action == "deny":
            violations.record("repetition_guard", "PreAction", tool, reason)
            return DecisionResult(
                decision=TypeCDecision.DENY,
                reason=reason,
                violation_name="repetition_guard",
            )
        elif config.action == "warn":
            violations.record_soft("repetition_guard", "PreAction", tool, reason)
            return None
        # log: no violation entry, just pass through
        return None

    return None
