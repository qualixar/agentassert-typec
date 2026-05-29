"""Final precise coverage closers."""


import pytest

from agentassert_typec_core.models.contract import (
    ContractSpecExtended, InvariantsExtended, ProcessInvariants,
    MustState, ProcessDrift, ContextBudget,
)
from agentassert_typec_core.models.session import SessionContext
from agentassert_typec_core.models.events import PreAction, TurnEnd, ContextWindow
from agentassert_typec_core.dsl.ast_compiler import CompiledContract
from agentassert_typec_core.monitor.drift import DriftTracker
from agentassert_typec_core.monitor.theta import ThetaScorer
from agentassert_typec_core.monitor.violation_log import ViolationLog
from agentassert_typec_core.evaluator.process_eval import (
    evaluate_must_state, evaluate_turn_end_soft,
)


class TestParserLine49:
    def test_parser_early_return_on_validator_errors(self, tmp_path):
        from agentassert_typec_core.dsl.parser import parse_contract

        p = tmp_path / "invalid.yaml"
        p.write_text("""dsl_version: '0.4'
contractspec: '1.0'
kind: agent
name: test
description: test
version: '0.1'
invariants:
  process:
    - tool_blocklist:
        tools: []
        scope: session
""")
        result = parse_contract(p)
        assert not result.is_valid
        assert "BLOCKLIST_EMPTY_TOOLS" in [e.code for e in result.errors]


class TestOperatorsImportFallbackBranch:
    def test_abc_evaluate_check_raise(self):
        import agentassert_typec_core.evaluator.operators as op
        saved = op.evaluate_check
        op.evaluate_check = None
        try:
            with pytest.raises(Exception, match="install agentassert-abc"):
                op.evaluate_abc_check({}, {})
        finally:
            op.evaluate_check = saved

    def test_abc_evaluate_check_success(self):
        import agentassert_typec_core.evaluator.operators as op
        saved = op.evaluate_check
        op.evaluate_check = lambda c, s: True
        try:
            result = op.evaluate_abc_check({"test": 1}, {"test": 1})
            assert result is True
        finally:
            op.evaluate_check = saved


class TestMustStatePatternNoMatch:
    def test_must_state_rule_pattern_no_match(self):
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="ms-nomatch", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    must_state=[MustState(field="cost", before_tool_pattern="tap_*")]
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        ctx = SessionContext(session_id="s1", stated_fields=frozenset())
        event = PreAction(session_id="s1", contract_id="c1", tool="Read", args={}, context=ctx)
        result = evaluate_must_state(event, compiled, ViolationLog())
        assert result is None


class TestDriftBelowThreshold:
    def test_drift_below_threshold_no_action(self):
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="drift-low", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    process_drift=ProcessDrift(window_size=5, jsd_threshold=0.9, action="log"),
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        drift = DriftTracker(window=5)
        for _ in range(10):
            drift.update(tool="OnlyTool")
        assert drift.current_jsd() < 0.5
        result = evaluate_turn_end_soft(
            TurnEnd(session_id="s1", contract_id="c1", assistant_output="x"),
            compiled, drift, ThetaScorer(), ViolationLog(),
        )
        assert result.decision.name == "ALLOW"


# ===================================================================
# Hit the implicit fallthrough: process_eval line 92→97 (warn action)
# and line 126→129 (theta_penalty action) via the engine dispatch path.
# ===================================================================

class TestBranchFallthrough:
    def test_context_budget_warn_fallthrough_through_engine(self):
        """Hit 92→97: 'warn' records soft violation then falls through to return ALLOW."""
        from agentassert_typec_core.evaluator.engine import dispatch_event
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="cb-warn-fall", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    context_budget=ContextBudget(max_tokens_per_turn=100, action_on_breach="warn"),
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        event = ContextWindow(session_id="s1", contract_id="c1", token_count=500, prefix_hash="x")
        result = dispatch_event(event, compiled, DriftTracker(), ThetaScorer(), ViolationLog())
        assert result.decision.name == "ALLOW"

    def test_drift_theta_penalty_fallthrough_through_engine(self):
        """Hit 126→129: theta_penalty applies and falls through to return ALLOW."""
        from agentassert_typec_core.evaluator.engine import dispatch_event
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="drift-theta-fall", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    process_drift=ProcessDrift(
                        window_size=3, jsd_threshold=0.05, action="theta_penalty",
                    ),
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        drift = DriftTracker(window=3)
        for _ in range(5):
            drift.update(tool="A")
        for _ in range(5):
            drift.update(tool="B")
        theta = ThetaScorer()
        event = TurnEnd(session_id="s1", contract_id="c1", assistant_output="x")
        result = dispatch_event(event, compiled, drift, theta, ViolationLog())
        assert result.decision.name == "ALLOW"
