"""Precise final coverage gaps — engine line 62, parser line 49, operators lines 9-14."""


from agentassert_typec_core.models.contract import (
    ContractSpecExtended, InvariantsExtended, ProcessInvariants,
    ToolBlocklist, MustState,
)
from agentassert_typec_core.models.session import SessionContext
from agentassert_typec_core.models.events import PreAction
from agentassert_typec_core.dsl.ast_compiler import CompiledContract
from agentassert_typec_core.evaluator.engine import dispatch_event
from agentassert_typec_core.monitor.drift import DriftTracker
from agentassert_typec_core.monitor.theta import ThetaScorer
from agentassert_typec_core.monitor.violation_log import ViolationLog


class TestPreciseGaps:
    def test_must_state_deny_through_dispatch_event(self):
        """Hit engine.py line 62: return result for must_state DENY via dispatch_event → _eval_pre_action."""
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="ms-dispatch", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    tool_blocklist=[ToolBlocklist(tools=["zzz"])],
                    must_state=[MustState(
                        field="cost", before_tool_pattern="tap_*",
                        rationale="Must state cost",
                    )],
                )
            ),
        )
        compiled = CompiledContract.from_spec(spec)
        ctx = SessionContext(session_id="s1", stated_fields=frozenset({"other"}))
        event = PreAction(
            session_id="s1", contract_id="c1", tool="tap_deepseek",
            args={}, context=ctx,
        )
        drift = DriftTracker()
        theta = ThetaScorer()
        violations = ViolationLog()
        result = dispatch_event(event, compiled, drift, theta, violations)
        assert result.is_deny()
        assert result.violation_name == "must_state"

    def test_parser_line_49_error_return(self, tmp_path):
        """Hit parser.py line 49: early return when errors exist."""
        from agentassert_typec_core.dsl.parser import parse_contract

        p = tmp_path / "missing_req.yaml"
        p.write_text("dsl_version: '0.4'\n")
        result = parse_contract(p)
        assert not result.is_valid
        assert result.contract is None
