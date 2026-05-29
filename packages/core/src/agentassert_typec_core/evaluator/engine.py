from __future__ import annotations

from agentassert_typec_core.dsl.ast_compiler import CompiledContract
from agentassert_typec_core.evaluator.process_eval import (
    evaluate_tool_blocklist,
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
) -> DecisionResult:
    if isinstance(event, PreAction):
        return _eval_pre_action(event, compiled, violations)
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
    violations: ViolationLog,
) -> DecisionResult:
    result = evaluate_tool_blocklist(event, compiled, violations)
    if result is not None:
        return result

    result = evaluate_must_state(event, compiled, violations)
    if result is not None:
        return result

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
