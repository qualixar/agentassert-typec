"""Cover new SessionMonitor features — judge dispatchers, turn/deny counts."""

from pathlib import Path

from agentassert_typec_core.models.contract import (
    ContractSpecExtended, InvariantsExtended, ProcessInvariants,
    ToolBlocklist, JudgePredicate,
)
from agentassert_typec_core.models.events import PreAction, TurnEnd
from agentassert_typec_core.monitor.session import SessionMonitor

FIXTURES = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "contracts"


class TestSessionMonitorJudge:
    def test_init_creates_judge_dispatchers(self):
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="judge-test", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    judge_predicate=[
                        JudgePredicate(rubric="Test rubric", sample_rate=0.3, model="haiku"),
                        JudgePredicate(rubric="Another", sample_rate=0.1, model="ds-flash-free"),
                    ]
                )
            ),
        )
        monitor = SessionMonitor(spec)
        assert len(monitor._judge_dispatchers) == 2

    def test_no_process_invariants_no_dispatchers(self):
        spec = ContractSpecExtended(
            contractspec="1.0", kind="agent",
            name="simple", description="test", version="0.1",
        )
        monitor = SessionMonitor(spec)
        assert len(monitor._judge_dispatchers) == 0

    def test_schedule_judge_evaluation_no_action(self):
        """schedule_judge_evaluation: judge with high sample rate dispatches correctly."""
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="judge-sample", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    judge_predicate=[
                        JudgePredicate(rubric="Test", sample_rate=1.0, model="haiku"),
                    ]
                )
            ),
        )
        monitor = SessionMonitor(spec)
        assert len(monitor._judge_dispatchers) == 1
        monitor.schedule_judge_evaluation("output", "s1")
        assert monitor._judge_dispatchers[0]._sample_count >= 1

    def test_turn_count_incremented_on_turnend(self):
        spec = ContractSpecExtended(
            contractspec="1.0", kind="agent",
            name="turn-test", description="test", version="0.1",
        )
        monitor = SessionMonitor(spec)
        assert monitor.turn_count == 0
        event = TurnEnd(session_id="s1", contract_id="c1", assistant_output="hello")
        monitor.evaluate(event)
        assert monitor.turn_count == 1

    def test_deny_count_incremented(self):
        spec = ContractSpecExtended(
            dsl_version="0.4", contractspec="1.0", kind="agent",
            name="deny-test", description="test", version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    tool_blocklist=[ToolBlocklist(tools=["rm"])],
                )
            ),
        )
        monitor = SessionMonitor(spec)
        assert monitor.deny_count == 0
        event = PreAction(session_id="s1", contract_id="c1", tool="rm", args={})
        result = monitor.evaluate(event)
        assert result.is_deny()
        assert monitor.deny_count == 1
