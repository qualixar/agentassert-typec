from __future__ import annotations

from agentassert_typec_core.dsl.ast_compiler import CompiledContract
from agentassert_typec_core.models.decisions import DecisionResult, TypeCDecision
from agentassert_typec_core.models.events import (
    PreAction,
    ContextWindow,
    TurnEnd,
)
from agentassert_typec_core.monitor.drift import DriftTracker
from agentassert_typec_core.monitor.theta import ThetaScorer
from agentassert_typec_core.monitor.violation_log import ViolationLog


def evaluate_tool_blocklist(
    event: PreAction,
    compiled: CompiledContract,
    violations: ViolationLog,
) -> DecisionResult | None:
    tool = event.tool
    for pattern in compiled.tool_blocklist_patterns:
        if pattern.search(tool):
            violations.record(
                name="tool_blocklist",
                event_type="PreAction",
                tool=tool,
                reason=f"Tool '{tool}' matches blocklist pattern '{pattern.pattern}'",
            )
            return DecisionResult(
                decision=TypeCDecision.DENY,
                reason=f"ContractBreach: tool_blocklist — '{tool}' is blocked",
                violation_name="tool_blocklist",
            )
    return None


def evaluate_must_precede(
    event: PreAction,
    compiled: CompiledContract,
    seen_session: set[str],
    seen_turn: set[str],
    violations: ViolationLog,
) -> DecisionResult | None:
    tool = event.tool
    for rule in compiled.must_precede_rules:
        if rule["after"] != tool:
            continue
        seen = seen_session if rule["scope"] == "session" else seen_turn
        if rule["before"] not in seen:
            reason = (
                f"ContractBreach: must_precede — '{rule['before']}' must be called "
                f"before '{tool}' (scope={rule['scope']})"
            )
            violations.record(
                name="must_precede",
                event_type="PreAction",
                tool=tool,
                reason=reason,
            )
            return DecisionResult(
                decision=TypeCDecision.DENY,
                reason=reason,
                violation_name="must_precede",
            )
    return None


def evaluate_tool_allowlist(
    event: PreAction,
    compiled: CompiledContract,
    violations: ViolationLog,
) -> DecisionResult | None:
    if not compiled.tool_allowlist_patterns:
        return None
    tool = event.tool
    for _scope, patterns in compiled.tool_allowlist_patterns:
        for pattern in patterns:
            if pattern.search(tool):
                return None
    violations.record(
        name="tool_allowlist",
        event_type="PreAction",
        tool=tool,
        reason=f"Tool '{tool}' not in any allowlist",
    )
    return DecisionResult(
        decision=TypeCDecision.DENY,
        reason=f"ContractBreach: tool_allowlist — '{tool}' is not permitted",
        violation_name="tool_allowlist",
    )


def evaluate_must_state(
    event: PreAction,
    compiled: CompiledContract,
    violations: ViolationLog,
) -> DecisionResult | None:
    tool = event.tool
    for rule in compiled.must_state_rules:
        for pattern in rule["patterns"]:
            if pattern.search(tool):
                ctx = event.context
                if ctx is None or not ctx.has_stated_field(rule["field"]):
                    violations.record(
                        name="must_state",
                        event_type="PreAction",
                        tool=tool,
                        reason=(
                            f"Field '{rule['field']}' not stated before '{tool}'. "
                            f"Rationale: {rule['rationale']}"
                        ),
                    )
                    return DecisionResult(
                        decision=TypeCDecision.DENY,
                        reason=(
                            f"ContractBreach: must_state — field '{rule['field']}' "
                            f"must be stated before calling '{tool}'. "
                            f"Rationale: {rule['rationale']}"
                        ),
                        violation_name="must_state",
                    )
    return None


def evaluate_context_budget(
    event: ContextWindow,
    compiled: CompiledContract,
    violations: ViolationLog,
) -> DecisionResult:
    if compiled.context_budget_limit and event.token_count > compiled.context_budget_limit:
        action = compiled.context_budget_action
        if action == "deny":
            return DecisionResult(
                decision=TypeCDecision.DENY,
                reason=(
                    f"ContractBreach: context_budget — "
                    f"{event.token_count} tokens exceeds limit {compiled.context_budget_limit}"
                ),
                violation_name="context_budget",
            )
        elif action == "warn":
            violations.record_soft(
                "context_budget",
                "ContextWindow",
                "context",
                f"{event.token_count} tokens > {compiled.context_budget_limit}",
            )
        elif action == "compress":
            return DecisionResult(
                decision=TypeCDecision.ALLOW,
                reason="compress_hint",
            )
    return DecisionResult(decision=TypeCDecision.ALLOW)


def evaluate_turn_end_soft(
    event: TurnEnd,
    compiled: CompiledContract,
    drift: DriftTracker,
    theta: ThetaScorer,
    violations: ViolationLog,
) -> DecisionResult:
    if compiled.process_drift_config:
        jsd = drift.current_jsd()
        config = compiled.process_drift_config
        if jsd > config.jsd_threshold:
            action = config.action
            if action == "log":
                violations.record_soft(
                    "process_drift",
                    "TurnEnd",
                    "n/a",
                    f"JSD {jsd:.3f} > threshold {config.jsd_threshold}",
                )
            elif action == "warn":
                violations.record_soft(
                    "process_drift",
                    "TurnEnd",
                    "n/a",
                    f"JSD {jsd:.3f} exceeds threshold",
                )
            elif action == "theta_penalty":
                theta.apply_penalty(0.05)

    return DecisionResult(decision=TypeCDecision.ALLOW)
