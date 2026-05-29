import pytest
from pydantic import ValidationError as PydanticError

from agentassert_typec_core.models.contract import (
    ToolBlocklist,
    ToolAllowlist,
    MustPrecede,
    MustState,
    ContextBudget,
    ProcessDrift,
    JudgePredicate,
    ProcessInvariants,
    InvariantsExtended,
    ContractSpecExtended,
    ConstraintCheck,
    HardConstraint,
)


class TestBlocklist:
    def test_tool_blocklist_construction(self):
        bl = ToolBlocklist(tools=["rm -rf /*", "curl|bash", "mkfs.*"])
        assert bl.tools == ["rm -rf /*", "curl|bash", "mkfs.*"]
        assert bl.scope == "session"

    def test_tool_blocklist_frozen(self):
        bl = ToolBlocklist(tools=["rm"])
        with pytest.raises(PydanticError):
            bl.scope = "turn"  # type: ignore
        with pytest.raises(PydanticError):
            bl.tools = ["new"]  # type: ignore

    def test_tool_blocklist_invalid_scope_raises(self):
        with pytest.raises((PydanticError, ValueError)):
            ToolBlocklist(tools=["rm"], scope="invalid")  # type: ignore

    def test_tool_blocklist_turn_scope(self):
        bl = ToolBlocklist(tools=["rm"], scope="turn")
        assert bl.scope == "turn"


class TestAllowlist:
    def test_tool_allowlist_construction(self):
        al = ToolAllowlist(tools=["Read", "Write", "Edit"])
        assert al.tools == ["Read", "Write", "Edit"]
        assert al.scope == "session"

    def test_tool_allowlist_frozen(self):
        al = ToolAllowlist(tools=["Read"])
        with pytest.raises(PydanticError):
            al.scope = "new_value"  # type: ignore


class TestMustPrecede:
    def test_must_precede_construction(self):
        mp = MustPrecede(before="challenge", after="recommendation")
        assert mp.before == "challenge"
        assert mp.after == "recommendation"
        assert mp.scope == "turn"

    def test_must_precede_frozen(self):
        mp = MustPrecede(before="challenge", after="recommendation")
        with pytest.raises(PydanticError):
            mp.before = "changed"  # type: ignore


class TestMustState:
    def test_must_state_construction(self):
        ms = MustState(
            field="cost",
            before_tool_pattern="tap_*",
            rationale="Cost required before paid API call",
        )
        assert ms.field == "cost"
        assert ms.before_tool_pattern == "tap_*"
        assert ms.rationale != ""

    def test_must_state_frozen(self):
        ms = MustState(field="cost", before_tool_pattern="tap_*")
        with pytest.raises(PydanticError):
            ms.field = "changed"  # type: ignore


class TestContextBudget:
    def test_context_budget_defaults(self):
        cb = ContextBudget()
        assert cb.max_tokens_per_turn == 60000
        assert cb.action_on_breach == "warn"

    def test_context_budget_custom(self):
        cb = ContextBudget(max_tokens_per_turn=30000, action_on_breach="deny")
        assert cb.max_tokens_per_turn == 30000
        assert cb.action_on_breach == "deny"

    def test_context_budget_frozen(self):
        cb = ContextBudget()
        with pytest.raises(PydanticError):
            cb.max_tokens_per_turn = 100  # type: ignore


class TestProcessDrift:
    def test_process_drift_defaults(self):
        pd = ProcessDrift()
        assert pd.window_size == 10
        assert pd.jsd_threshold == 0.3
        assert pd.action == "log"

    def test_process_drift_frozen(self):
        pd = ProcessDrift()
        with pytest.raises(PydanticError):
            pd.jsd_threshold = 0.5  # type: ignore


class TestJudgePredicate:
    def test_judge_predicate_construction(self):
        jp = JudgePredicate(
            rubric="Response shows conviction",
            sample_rate=0.2,
            model="haiku",
        )
        assert jp.rubric == "Response shows conviction"
        assert jp.sample_rate == 0.2
        assert jp.model == "haiku"
        assert jp.action_on_fail == "theta_penalty"
        assert jp.cost_ceiling_usd_per_session == 0.10

    def test_judge_predicate_frozen(self):
        jp = JudgePredicate(rubric="Test")
        with pytest.raises(PydanticError):
            jp.sample_rate = 1.0  # type: ignore


class TestProcessInvariants:
    def test_empty_process_invariants(self):
        pi = ProcessInvariants()
        assert pi.must_precede == []
        assert pi.must_state == []
        assert pi.tool_blocklist == []
        assert pi.tool_allowlist == []
        assert pi.context_budget is None
        assert pi.process_drift is None
        assert pi.judge_predicate == []

    def test_populated_process_invariants(self):
        pi = ProcessInvariants(
            tool_blocklist=[ToolBlocklist(tools=["rm"])],
            context_budget=ContextBudget(max_tokens_per_turn=50000),
        )
        assert len(pi.tool_blocklist) == 1
        assert pi.context_budget.max_tokens_per_turn == 50000

    def test_frozen(self):
        pi = ProcessInvariants()
        with pytest.raises(PydanticError):
            pi.tool_blocklist = []  # type: ignore


class TestContractSpecExtended:
    def test_minimal_contract(self):
        spec = ContractSpecExtended(
            contractspec="1.0",
            kind="agent",
            name="test-contract",
            description="A test contract",
            version="0.1",
        )
        assert spec.dsl_version == "0.3"
        assert spec.name == "test-contract"
        assert spec.kind == "agent"

    def test_type_c_contract(self):
        spec = ContractSpecExtended(
            dsl_version="0.4",
            contractspec="1.0",
            kind="agent",
            name="type-c-contract",
            description="Type-C test",
            version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    tool_blocklist=[ToolBlocklist(tools=["rm"])],
                )
            ),
        )
        assert spec.dsl_version == "0.4"
        assert spec.invariants is not None
        assert spec.invariants.process is not None
        assert len(spec.invariants.process.tool_blocklist) == 1

    def test_frozen(self):
        spec = ContractSpecExtended(
            contractspec="1.0",
            kind="agent",
            name="test",
            description="test",
            version="0.1",
        )
        with pytest.raises(PydanticError):
            spec.name = "changed"  # type: ignore

    def test_abc_invariants_extended(self):
        spec = ContractSpecExtended(
            contractspec="1.0",
            kind="agent",
            name="abc-style",
            description="ABC style with hard constraints",
            version="0.1",
            invariants=InvariantsExtended(
                hard=[
                    HardConstraint(
                        name="no-pii",
                        description="No PII in output",
                        check=ConstraintCheck(field="output.pii_detected", equals=False),
                    )
                ],
            ),
        )
        assert len(spec.invariants.hard) == 1
        assert spec.invariants.hard[0].name == "no-pii"
