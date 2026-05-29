from __future__ import annotations

from collections import deque
from collections import defaultdict
from typing import Any

from agentassert_typec_core.dsl.ast_compiler import CompiledContract
from agentassert_typec_core.evaluator.process_eval import (
    evaluate_tool_blocklist,
    evaluate_tool_allowlist,
    evaluate_must_precede,
    evaluate_must_state,
    evaluate_context_budget,
    evaluate_turn_end_soft,
)
from agentassert_typec_core.models.decisions import DecisionResult, TypeCDecision
from agentassert_typec_core.models.events import (
    TypeCEvent,
    PreAction,
    PostAction,
    TurnStart,
    TurnEnd,
    SessionStart,
    SessionEnd,
    ContextWindow,
)
from agentassert_typec_core.monitor.drift import DriftTracker
from agentassert_typec_core.monitor.theta import ThetaScorer
from agentassert_typec_core.monitor.violation_log import ViolationLog


def dispatch_event(
    event: TypeCEvent,
    compiled: CompiledContract,
    drift: DriftTracker,
    theta: ThetaScorer,
    violations: ViolationLog,
    seen_session: set[str] | None = None,
    seen_turn: set[str] | None = None,
    accumulated_cost: float = 0.0,
    tool_history: deque | None = None,
    seq_hash_counts: dict | None = None,
) -> DecisionResult:
    _seen_session = seen_session if seen_session is not None else set()
    _seen_turn = seen_turn if seen_turn is not None else set()
    _tool_history = tool_history if tool_history is not None else deque()
    _seq_hash_counts = seq_hash_counts if seq_hash_counts is not None else defaultdict(int)

    if isinstance(event, PreAction):
        return _eval_pre_action(
            event, compiled, _seen_session, _seen_turn, violations,
            accumulated_cost, _tool_history, _seq_hash_counts,
        )
    elif isinstance(event, PostAction):
        return _eval_post_action(event, drift, theta)
    elif isinstance(event, TurnStart):
        return DecisionResult(decision=TypeCDecision.ALLOW)
    elif isinstance(event, TurnEnd):
        return _eval_turn_end(event, compiled, drift, theta, violations)
    elif isinstance(event, ContextWindow):
        return evaluate_context_budget(event, compiled, violations)
    elif isinstance(event, SessionStart):
        return DecisionResult(decision=TypeCDecision.ALLOW, reason="session started")
    elif isinstance(event, SessionEnd):
        return DecisionResult(decision=TypeCDecision.ALLOW, reason="session ended")
    else:
        return DecisionResult(decision=TypeCDecision.ALLOW, reason="unknown event type")


def _eval_pre_action(
    event: PreAction,
    compiled: CompiledContract,
    seen_session: set[str],
    seen_turn: set[str],
    violations: ViolationLog,
    accumulated_cost: float = 0.0,
    tool_history: deque | None = None,
    seq_hash_counts: dict | None = None,
) -> DecisionResult:
    from agentassert_typec_core.evaluator.content_eval import (
        evaluate_cost_ceiling,
        evaluate_repetition_guard,
    )

    # 1. Tool blocklist
    result = evaluate_tool_blocklist(event, compiled, violations)
    if result is not None:
        return result

    # 2. Must precede
    result = evaluate_must_precede(event, compiled, seen_session, seen_turn, violations)
    if result is not None:
        return result

    # 3. Tool allowlist
    result = evaluate_tool_allowlist(event, compiled, violations)
    if result is not None:
        return result

    # 4. Cost ceiling
    result = evaluate_cost_ceiling(event, compiled, accumulated_cost, violations)
    if result is not None:
        return result

    # 5. Repetition guard
    _history = tool_history if tool_history is not None else deque()
    _counts = seq_hash_counts if seq_hash_counts is not None else {}
    result = evaluate_repetition_guard(event, compiled, _history, _counts, violations)
    if result is not None:
        return result

    # 6. Must state
    result = evaluate_must_state(event, compiled, violations)
    if result is not None:
        return result

    # 7. Allow
    return DecisionResult(decision=TypeCDecision.ALLOW)


def _eval_post_action(
    event: PostAction,
    drift: DriftTracker,
    theta: ThetaScorer,
) -> DecisionResult:
    drift.update(tool=event.tool, state=event.state)
    theta.record_action(tool=event.tool)
    return DecisionResult(decision=TypeCDecision.ALLOW)


def _eval_turn_end(
    event: TurnEnd,
    compiled: CompiledContract,
    drift: DriftTracker,
    theta: ThetaScorer,
    violations: ViolationLog,
) -> DecisionResult:
    return evaluate_turn_end_soft(event, compiled, drift, theta, violations)
