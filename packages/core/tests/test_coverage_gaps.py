"""Comprehensive tests to close 100% coverage gaps — evaluator, exceptions, models, monitor."""

import json
from pathlib import Path

import pytest

from agentassert_typec_core.models.contract import (
    ContractSpecExtended,
    InvariantsExtended,
    ProcessInvariants,
    MustState,
    ContextBudget,
    ProcessDrift,
    HardConstraint,
    SoftConstraint,
    ConstraintCheck,
    ReliabilityWeights,
)
from agentassert_typec_core.models.session import SessionContext
from agentassert_typec_core.models.events import (
    PreAction,
    TurnEnd,
    SessionStart,
    SessionEnd,
    ContextWindow,
    TypeCEvent,
)
from agentassert_typec_core.models.decisions import DecisionResult, TypeCDecision
from agentassert_typec_core.models.session import HistoryDigest, DriftReport
from agentassert_typec_core.dsl.ast_compiler import CompiledContract
from agentassert_typec_core.dsl.parser import parse_contract
from agentassert_typec_core.monitor.drift import DriftTracker
from agentassert_typec_core.monitor.theta import ThetaScorer
from agentassert_typec_core.monitor.violation_log import ViolationLog
from agentassert_typec_core.evaluator.engine import dispatch_event
from agentassert_typec_core.evaluator.process_eval import (
    evaluate_must_state,
    evaluate_context_budget,
    evaluate_turn_end_soft,
)
from agentassert_typec_core.exceptions import (
    ContractBreachError,
    ContractLoadError,
    PredicateEvalError,
)

FIXTURES = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "contracts"


# ===================================================================
# COV-01: evaluator/operators.py — ABC re-export (lines 1-22)
# ===================================================================

class TestOperatorsABC:
    def test_has_abc_returns_false_when_not_installed(self):
        """Directly calls _has_abc() to cover its return False body (line 14).
        Must run BEFORE the test that replaces _has_abc with a lambda."""
        import agentassert_typec_core.evaluator.operators as op_mod
        result = op_mod._has_abc()
        assert result is False

    def test_import_available_falls_back_gracefully(self):
        """If agentassert_abc not installed, evaluate_abc_check raises ContractLoadError."""
        import agentassert_typec_core.evaluator.operators as op_mod
        original_has_abc = op_mod._has_abc
        original_evaluate_check = op_mod.evaluate_check
        try:
            op_mod.evaluate_check = None
            op_mod._has_abc = lambda: False
            with pytest.raises(ContractLoadError, match="install agentassert-abc"):
                op_mod.evaluate_abc_check({}, {})
        finally:
            op_mod._has_abc = original_has_abc
            op_mod.evaluate_check = original_evaluate_check


# ===================================================================
# COV-02: evaluator/engine.py — SessionStart, SessionEnd, bare TypeCEvent, TurnEnd
# ===================================================================

class TestEvaluatorEngineGaps:
    def test_session_start_dispatch(self):
        compiled = CompiledContract.from_spec(_empty_spec())
        event = SessionStart(
            session_id="s1", contract_id="c1", workdir="/tmp", model="claude",
        )
        result = dispatch_event(event, compiled, DriftTracker(), ThetaScorer(), ViolationLog())
        assert result.decision == TypeCDecision.ALLOW
        assert result.reason == "session started"

    def test_session_end_dispatch(self):
        compiled = CompiledContract.from_spec(_empty_spec())
        event = SessionEnd(session_id="s1", contract_id="c1", theta=0.95)
        result = dispatch_event(event, compiled, DriftTracker(), ThetaScorer(), ViolationLog())
        assert result.decision == TypeCDecision.ALLOW
        assert result.reason == "session ended"

    def test_bare_type_c_event_dispatch(self):
        compiled = CompiledContract.from_spec(_empty_spec())
        event = TypeCEvent(session_id="s1", contract_id="c1")
        result = dispatch_event(event, compiled, DriftTracker(), ThetaScorer(), ViolationLog())
        assert result.decision == TypeCDecision.ALLOW
        assert result.reason == "unknown event type"

    def test_turn_end_with_drift_config_log(self):
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="drift-log", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    process_drift=ProcessDrift(window_size=3, jsd_threshold=0.1, action="log"),
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        drift = DriftTracker(window=3)
        for _ in range(5):
            drift.update(tool="Read")
        for _ in range(5):
            drift.update(tool="Write")
        theta = ThetaScorer()
        violations = ViolationLog()
        event = TurnEnd(session_id="s1", contract_id="c1", assistant_output="test")
        result = dispatch_event(event, compiled, drift, theta, violations)
        assert result.decision == TypeCDecision.ALLOW
        assert len(violations.all_violations()) >= 1

    def test_turn_end_with_drift_config_warn(self):
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="drift-warn", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    process_drift=ProcessDrift(window_size=3, jsd_threshold=0.1, action="warn"),
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        drift = DriftTracker(window=3)
        for _ in range(5):
            drift.update(tool="Read")
        for _ in range(5):
            drift.update(tool="Write")
        theta = ThetaScorer()
        violations = ViolationLog()
        event = TurnEnd(session_id="s1", contract_id="c1", assistant_output="test")
        result = dispatch_event(event, compiled, drift, theta, violations)
        assert result.decision == TypeCDecision.ALLOW
        assert len(violations.all_violations()) >= 1

    def test_turn_end_with_drift_config_theta_penalty(self):
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="drift-penalty", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    process_drift=ProcessDrift(window_size=3, jsd_threshold=0.1, action="theta_penalty"),
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        drift = DriftTracker(window=3)
        for _ in range(5):
            drift.update(tool="Read")
        for _ in range(5):
            drift.update(tool="Write")
        theta = ThetaScorer()
        violations = ViolationLog()
        event = TurnEnd(session_id="s1", contract_id="c1", assistant_output="test")
        result = dispatch_event(event, compiled, drift, theta, violations)
        assert result.decision == TypeCDecision.ALLOW
        assert theta.compute() < 1.0

    def test_turn_end_no_drift_config(self):
        compiled = CompiledContract.from_spec(_contract_with_context_budget(
            "warn", 10000,
        ))
        drift = DriftTracker()
        theta = ThetaScorer()
        violations = ViolationLog()
        event = TurnEnd(session_id="s1", contract_id="c1", assistant_output="test")
        result = dispatch_event(event, compiled, drift, theta, violations)
        assert result.decision == TypeCDecision.ALLOW


# ===================================================================
# COV-03: evaluator/process_eval.py — must_state DENY, compress, drift paths
# ===================================================================

class TestProcessEvalGaps:
    def test_must_state_deny(self):
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="ms-deny", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    must_state=[MustState(
                        field="cost", before_tool_pattern="tap_*",
                        rationale="Must state cost before paid API",
                    )]
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        violations = ViolationLog()
        ctx = SessionContext(session_id="s1", stated_fields=frozenset({"other_field"}))
        event = PreAction(
            session_id="s1", contract_id="c1", tool="tap_deepseek",
            args={}, context=ctx,
        )
        result = evaluate_must_state(event, compiled, violations)
        assert result is not None
        assert result.is_deny()
        assert result.violation_name == "must_state"

    def test_must_state_no_context_denies(self):
        """Fail-secure: no context = no evidence field was stated = DENY."""
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="ms-nocontext", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    must_state=[MustState(
                        field="cost", before_tool_pattern="tap_*",
                    )]
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        violations = ViolationLog()
        event = PreAction(
            session_id="s1", contract_id="c1", tool="tap_deepseek",
            args={}, context=None,
        )
        result = evaluate_must_state(event, compiled, violations)
        assert result is not None
        assert result.is_deny()
        assert result.violation_name == "must_state"

    def test_context_budget_compress(self):
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="cb-compress", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    context_budget=ContextBudget(
                        max_tokens_per_turn=100, action_on_breach="compress",
                    )
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        violations = ViolationLog()
        event = ContextWindow(session_id="s1", contract_id="c1", token_count=500, prefix_hash="abc")
        result = evaluate_context_budget(event, compiled, violations)
        assert result.decision == TypeCDecision.ALLOW
        assert result.reason == "compress_hint"

    def test_context_budget_within_limit(self):
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="cb-ok", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    context_budget=ContextBudget(max_tokens_per_turn=100000),
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        violations = ViolationLog()
        event = ContextWindow(session_id="s1", contract_id="c1", token_count=500, prefix_hash="abc")
        result = evaluate_context_budget(event, compiled, violations)
        assert result.decision == TypeCDecision.ALLOW

    def test_evaluate_turn_end_soft_log_action(self):
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="drift-log-2", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    process_drift=ProcessDrift(window_size=3, jsd_threshold=0.1, action="log"),
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        drift = DriftTracker(window=3)
        for _ in range(5):
            drift.update(tool="Read")
        for _ in range(5):
            drift.update(tool="Write")
        theta = ThetaScorer()
        violations = ViolationLog()
        event = TurnEnd(session_id="s1", contract_id="c1", assistant_output="test")
        result = evaluate_turn_end_soft(event, compiled, drift, theta, violations)
        assert result.decision == TypeCDecision.ALLOW
        assert len(violations.all_violations()) >= 1

    def test_evaluate_turn_end_soft_warn_action(self):
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="drift-warn-2", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    process_drift=ProcessDrift(window_size=3, jsd_threshold=0.1, action="warn"),
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        drift = DriftTracker(window=3)
        for _ in range(5):
            drift.update(tool="Read")
        for _ in range(5):
            drift.update(tool="Write")
        theta = ThetaScorer()
        violations = ViolationLog()
        event = TurnEnd(session_id="s1", contract_id="c1", assistant_output="test")
        result = evaluate_turn_end_soft(event, compiled, drift, theta, violations)
        assert result.decision == TypeCDecision.ALLOW

    def test_evaluate_turn_end_soft_theta_penalty_action(self):
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="drift-theta-2", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    process_drift=ProcessDrift(window_size=3, jsd_threshold=0.1, action="theta_penalty"),
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        drift = DriftTracker(window=3)
        for _ in range(5):
            drift.update(tool="Read")
        for _ in range(5):
            drift.update(tool="Write")
        theta = ThetaScorer()
        violations = ViolationLog()
        event = TurnEnd(session_id="s1", contract_id="c1", assistant_output="test")
        result = evaluate_turn_end_soft(event, compiled, drift, theta, violations)
        assert result.decision == TypeCDecision.ALLOW
        assert theta.compute() < 1.0

    def test_evaluate_turn_end_soft_no_config(self):
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="no-drift", description="test", version="0.1",
            invariants=InvariantsExtended(process=ProcessInvariants()),
        )
        compiled = CompiledContract.from_spec(spec)
        drift = DriftTracker()
        theta = ThetaScorer()
        violations = ViolationLog()
        event = TurnEnd(session_id="s1", contract_id="c1", assistant_output="test")
        result = evaluate_turn_end_soft(event, compiled, drift, theta, violations)
        assert result.decision == TypeCDecision.ALLOW


# ===================================================================
# COV-04: exceptions.py — to_dict, to_json, to_http_body (lines 17, 20, 23)
# ===================================================================

class TestExceptions:
    def test_contract_breach_error_to_dict(self):
        e = ContractBreachError(
            violation_name="test", reason="bad", tool="rm",
            session_id="s1", contract_id="c1",
        )
        d = e.to_dict()
        assert d["violation_name"] == "test"
        assert d["decision"] == "deny"

    def test_contract_breach_error_to_json(self):
        e = ContractBreachError(
            violation_name="test", reason="bad", tool="rm",
            session_id="s1", contract_id="c1",
        )
        j = e.to_json()
        parsed = json.loads(j)
        assert parsed["violation_name"] == "test"

    def test_contract_breach_error_to_http_body(self):
        e = ContractBreachError(
            violation_name="test", reason="bad", tool="rm",
            session_id="s1", contract_id="c1",
        )
        body = e.to_http_body()
        assert body["error"] == "ContractBreachError"
        assert body["violation"] == "test"
        assert body["tool"] == "rm"

    def test_contract_load_error(self):
        with pytest.raises(ContractLoadError):
            raise ContractLoadError("bad contract")

    def test_predicate_eval_error(self):
        with pytest.raises(PredicateEvalError):
            raise PredicateEvalError("eval failed")


# ===================================================================
# COV-05: models/decisions.py — is_modify (line 26)
# ===================================================================

class TestDecisionResult:
    def test_is_modify_true(self):
        dr = DecisionResult(decision=TypeCDecision.MODIFY)
        assert dr.is_modify()
        assert not dr.is_deny()

    def test_is_modify_false_for_allow(self):
        dr = DecisionResult(decision=TypeCDecision.ALLOW)
        assert not dr.is_modify()

    def test_is_modify_false_for_deny(self):
        dr = DecisionResult(decision=TypeCDecision.DENY)
        assert not dr.is_modify()


# ===================================================================
# COV-06: models/session.py — has_stated_field True (line 14)
# ===================================================================

class TestSessionContext:
    def test_has_stated_field_true(self):
        ctx = SessionContext(
            session_id="s1",
            stated_fields=frozenset({"cost", "reason"}),
        )
        assert ctx.has_stated_field("cost")
        assert ctx.has_stated_field("reason")
        assert not ctx.has_stated_field("unknown")

    def test_session_context_defaults(self):
        ctx = SessionContext(session_id="s1")
        assert ctx.turn_index == 0
        assert ctx.token_count == 0


# ===================================================================
# COV-07: dsl/ast_compiler.py — soft constraint ABC compilation (lines 95, 100)
# ===================================================================

class TestAstCompilerABCSoftChecks:
    def test_soft_expr_check_compiled(self):
        spec = ContractSpecExtended(
            contractspec="1.0", kind="agent",
            name="soft-expr", description="test", version="0.1",
            invariants=InvariantsExtended(
                soft=[SoftConstraint(
                    name="latency",
                    check=ConstraintCheck(field="latency_ms", expr="latency_ms < 5000"),
                )]
            ),
        )
        cc = CompiledContract.from_spec(spec)
        assert len(cc.soft_checks) == 1
        assert cc.soft_checks[0][0] == "expr"

    def test_soft_struct_check_compiled(self):
        spec = ContractSpecExtended(
            contractspec="1.0", kind="agent",
            name="soft-struct", description="test", version="0.1",
            invariants=InvariantsExtended(
                soft=[SoftConstraint(
                    name="fast",
                    check=ConstraintCheck(field="latency_ms", lt=5000),
                )]
            ),
        )
        cc = CompiledContract.from_spec(spec)
        assert len(cc.soft_checks) == 1
        assert cc.soft_checks[0][0] == "struct"

    def test_hard_expr_check_compiled(self):
        spec = ContractSpecExtended(
            contractspec="1.0", kind="agent",
            name="hard-expr", description="test", version="0.1",
            invariants=InvariantsExtended(
                hard=[HardConstraint(
                    name="no-pii",
                    check=ConstraintCheck(field="pii", expr="pii == 0"),
                )]
            ),
        )
        cc = CompiledContract.from_spec(spec)
        assert len(cc.hard_checks) == 1
        assert cc.hard_checks[0][0] == "expr"

    def test_hard_struct_check_compiled(self):
        spec = ContractSpecExtended(
            contractspec="1.0", kind="agent",
            name="hard-struct", description="test", version="0.1",
            invariants=InvariantsExtended(
                hard=[HardConstraint(
                    name="no-pii",
                    check=ConstraintCheck(field="pii", equals=False),
                )]
            ),
        )
        cc = CompiledContract.from_spec(spec)
        assert len(cc.hard_checks) == 1
        assert cc.hard_checks[0][0] == "struct"


# ===================================================================
# COV-08: dsl/parser.py — model validation error path (line 49)
# ===================================================================

class TestParserModelValidationError:
    def test_model_validation_error_path(self, tmp_path):
        contract = tmp_path / "bad.yaml"
        contract.write_text("dsl_version: '0.4'\ncontractspec: '1.0'\nkind: unknown\nname: test\ndescription: test\nversion: '0.1'\n")
        result = parse_contract(contract)
        assert not result.is_valid
        assert any(e.code == "MODEL_VALIDATION_ERROR" for e in result.errors)


# ===================================================================
# COV-09: monitor/theta.py — record_drift, custom weights, recovery (lines 21, 44-47)
# ===================================================================

class TestThetaScorerGaps:
    def test_record_drift(self):
        scorer = ThetaScorer()
        scorer.record_drift(0.3)
        scorer.record_drift(0.5)
        theta = scorer.compute()
        assert theta < 1.0

    def test_custom_weights(self):
        weights = ReliabilityWeights(
            compliance=0.40, drift=0.20, event_freq=0.10, recovery_success=0.30,
        )
        scorer = ThetaScorer(weights=weights)
        assert scorer.compute() == 1.0

    def test_record_violation(self):
        scorer = ThetaScorer()
        scorer.record_violation()
        scorer.record_violation()
        scorer.record_violation()
        assert scorer.compute() < 1.0

    def test_record_recovery_success_and_failure(self):
        scorer = ThetaScorer()
        scorer.record_recovery(True)
        scorer.record_recovery(False)
        assert scorer.compute() < 1.0

    def test_record_recovery_all_success(self):
        scorer = ThetaScorer()
        scorer.record_recovery(True)
        scorer.record_recovery(True)
        assert scorer.compute() == 1.0


# ===================================================================
# COV-10: models/contract.py — model_validator edge cases (lines 199, 216)
# ===================================================================

class TestContractModelValidatorEdgeCases:
    def test_non_dict_data_passes_through(self):
        from agentassert_typec_core.models.contract import InvariantsExtended
        result = InvariantsExtended._coerce_process_from_list.__func__(InvariantsExtended, "not_a_dict")
        assert result == "not_a_dict"

    def test_process_none_passes_through(self):
        from agentassert_typec_core.models.contract import InvariantsExtended
        result = InvariantsExtended._coerce_process_from_list.__func__(InvariantsExtended, {"process": None, "hard": []})
        assert result["process"] is None

    def test_non_dict_op_skipped(self):
        from agentassert_typec_core.models.contract import _list_to_process_invariants
        result = _list_to_process_invariants([{"tool_blocklist": {"tools": ["rm"]}}, "not_a_dict", 42])
        assert len(result["tool_blocklist"]) == 1

    def test_process_each_operator_type(self):
        from agentassert_typec_core.models.contract import _list_to_process_invariants
        ops = [
            {"tool_blocklist": {"tools": ["rm"]}},
            {"tool_allowlist": {"tools": ["Read"], "scope": "session"}},
            {"must_precede": {"before": "a", "after": "b"}},
            {"must_state": {"field": "cost", "before_tool_pattern": "tap_*"}},
            {"judge_predicate": {"rubric": "test"}},
            {"context_budget": {"max_tokens_per_turn": 1000}},
            {"process_drift": {"action": "log"}},
        ]
        result = _list_to_process_invariants(ops)
        assert len(result["tool_blocklist"]) == 1
        assert len(result["tool_allowlist"]) == 1
        assert len(result["must_precede"]) == 1
        assert len(result["must_state"]) == 1
        assert len(result["judge_predicate"]) == 1
        assert result["context_budget"] == {"max_tokens_per_turn": 1000}
        assert result["process_drift"] == {"action": "log"}

    def test_history_digest_and_drift_report(self):
        hd = HistoryDigest(turn_count=5, total_tokens=25000, role_pattern="U-A-U-A")
        assert hd.turn_count == 5
        assert hd.total_tokens == 25000

        dr = DriftReport(current_jsd=0.15, window_size=10, violation_count=2)
        assert dr.current_jsd == 0.15
        assert dr.violation_count == 2


# ===================================================================
# Utilities
# ===================================================================

def _empty_spec() -> ContractSpecExtended:
    return ContractSpecExtended(
        contractspec="1.0", kind="agent", name="empty",
        description="empty", version="0.1",
    )


def _contract_with_context_budget(action: str, limit: int) -> ContractSpecExtended:
    return ContractSpecExtended(
        dsl_version="0.4", contractspec="1.0", kind="agent",
        name="cb-test", description="test", version="0.1",
        invariants=InvariantsExtended(
            process=ProcessInvariants(
                context_budget=ContextBudget(max_tokens_per_turn=limit, action_on_breach=action),
            )
        ),
    )
