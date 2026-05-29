from pathlib import Path

import pytest

from agentassert_typec_core.models.contract import (
    ContractSpecExtended,
    InvariantsExtended,
    ProcessInvariants,
    ToolBlocklist,
    ContextBudget,
)
from agentassert_typec_core.models.events import (
    PreAction,
    PostAction,
    TurnStart,
    ContextWindow,
)
from agentassert_typec_core.monitor.session import SessionMonitor
from agentassert_typec_core.models.decisions import TypeCDecision
from agentassert_typec_core.dsl.ast_compiler import CompiledContract
from agentassert_typec_core.evaluator.engine import dispatch_event
from agentassert_typec_core.monitor.drift import DriftTracker
from agentassert_typec_core.monitor.theta import ThetaScorer
from agentassert_typec_core.monitor.violation_log import ViolationLog

FIXTURES = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "contracts"


@pytest.fixture
def blocklist_contract():
    return ContractSpecExtended(
        dsl_version="0.4",
        contractspec="1.0",
        kind="agent",
        name="blocklist-test",
        description="test",
        version="0.1",
        invariants=InvariantsExtended(
            process=ProcessInvariants(
                tool_blocklist=[ToolBlocklist(tools=["rm", "curl|bash"])]
            )
        ),
    )


@pytest.fixture
def warn_budget_contract():
    return ContractSpecExtended(
        dsl_version="0.4",
        contractspec="1.0",
        kind="agent",
        name="budget-test",
        description="test",
        version="0.1",
        invariants=InvariantsExtended(
            process=ProcessInvariants(
                context_budget=ContextBudget(max_tokens_per_turn=100, action_on_breach="warn")
            )
        ),
    )


@pytest.fixture
def deny_budget_contract():
    return ContractSpecExtended(
        dsl_version="0.4",
        contractspec="1.0",
        kind="agent",
        name="budget-deny",
        description="test",
        version="0.1",
        invariants=InvariantsExtended(
            process=ProcessInvariants(
                context_budget=ContextBudget(max_tokens_per_turn=100, action_on_breach="deny")
            )
        ),
    )


@pytest.fixture
def empty_monitor():
    spec = ContractSpecExtended(
        contractspec="1.0",
        kind="agent",
        name="empty",
        description="empty",
        version="0.1",
    )
    return SessionMonitor(spec)


class TestEvaluatorEngine:
    def test_pre_action_blocked_tool(self, blocklist_contract):
        compiled = CompiledContract.from_spec(blocklist_contract)
        drift = DriftTracker()
        theta = ThetaScorer()
        violations = ViolationLog()

        event = PreAction(session_id="s1", contract_id="c1", tool="rm", args={})
        result = dispatch_event(event, compiled, drift, theta, violations)
        assert result.is_deny()
        assert result.violation_name == "tool_blocklist"

    def test_pre_action_allowed_tool(self, blocklist_contract):
        compiled = CompiledContract.from_spec(blocklist_contract)
        drift = DriftTracker()
        theta = ThetaScorer()
        violations = ViolationLog()

        event = PreAction(session_id="s1", contract_id="c1", tool="Read", args={})
        result = dispatch_event(event, compiled, drift, theta, violations)
        assert result.decision == TypeCDecision.ALLOW

    def test_pre_action_blocklist_or_pattern(self, blocklist_contract):
        compiled = CompiledContract.from_spec(blocklist_contract)
        drift = DriftTracker()
        theta = ThetaScorer()
        violations = ViolationLog()

        for tool in ["curl", "bash", "curl some args"]:
            event = PreAction(session_id="s1", contract_id="c1", tool=tool, args={})
            result = dispatch_event(event, compiled, drift, theta, violations)
            assert result.is_deny(), f"tool '{tool}' should be blocked"

    def test_post_action_allows_and_updates_drift(self):
        spec = ContractSpecExtended(
            contractspec="1.0", kind="agent", name="test", description="test", version="0.1",
        )
        compiled = CompiledContract.from_spec(spec)
        drift = DriftTracker(window=50)
        theta = ThetaScorer()
        violations = ViolationLog()

        event = PostAction(
            session_id="s1", contract_id="c1", tool="Read",
            args={"path": "/tmp"}, state={"bytes": 100},
        )
        result = dispatch_event(event, compiled, drift, theta, violations)
        assert result.decision == TypeCDecision.ALLOW

    def test_context_window_deny(self, deny_budget_contract):
        compiled = CompiledContract.from_spec(deny_budget_contract)
        drift = DriftTracker()
        theta = ThetaScorer()
        violations = ViolationLog()

        event = ContextWindow(session_id="s1", contract_id="c1", token_count=500, prefix_hash="abc")
        result = dispatch_event(event, compiled, drift, theta, violations)
        assert result.is_deny()
        assert result.violation_name == "context_budget"

    def test_context_window_warn(self, warn_budget_contract):
        compiled = CompiledContract.from_spec(warn_budget_contract)
        drift = DriftTracker()
        theta = ThetaScorer()
        violations = ViolationLog()

        event = ContextWindow(session_id="s1", contract_id="c1", token_count=500, prefix_hash="abc")
        result = dispatch_event(event, compiled, drift, theta, violations)
        assert result.decision == TypeCDecision.ALLOW
        assert len(violations.all_violations()) == 1
        assert violations.all_violations()[0]["kind"] == "soft"

    def test_unknown_event_type_allows(self, empty_monitor):
        event = TurnStart(session_id="s1", contract_id="c1", user_input="hello")
        result = empty_monitor.evaluate(event)
        assert result.decision == TypeCDecision.ALLOW


class TestSessionMonitor:
    def test_from_yaml_valid(self):
        monitor = SessionMonitor.from_yaml(str(FIXTURES / "safety-minimal.yaml"))
        assert monitor is not None

    def test_from_yaml_invalid(self):
        with pytest.raises(Exception):
            SessionMonitor.from_yaml(str(FIXTURES / "invalid-missing-name.yaml"))

    def test_concurrent_evaluate(self, empty_monitor):
        import threading

        results = []
        errors = []

        def make_call():
            try:
                event = PreAction(session_id="s1", contract_id="c1", tool="Read", args={})
                r = empty_monitor.evaluate(event)
                results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=make_call) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 10
        assert all(r.decision == TypeCDecision.ALLOW for r in results)

    def test_close_returns_session_end(self, empty_monitor):
        result = empty_monitor.close()
        assert result.theta > 0

    def test_abc_compat_contract(self):
        monitor = SessionMonitor.from_yaml(str(FIXTURES / "abc-v03-compat.yaml"))
        event = PreAction(session_id="s1", contract_id="c1", tool="Read", args={})
        result = monitor.evaluate(event)
        assert result.decision == TypeCDecision.ALLOW
