
import pytest

from agentassert_typec_core.dsl.ast_compiler import CompiledContract
from agentassert_typec_core.models.contract import (
    ContractSpecExtended,
    InvariantsExtended,
    ProcessInvariants,
    ToolBlocklist,
    ToolAllowlist,
    MustState,
    MustPrecede,
    ContextBudget,
    ProcessDrift,
    JudgePredicate,
)


@pytest.fixture
def minimal_spec():
    return ContractSpecExtended(
        dsl_version="0.4",
        contractspec="1.0",
        kind="agent",
        name="test",
        description="test",
        version="0.1",
    )


class TestCompiledContract:
    def test_empty_spec(self, minimal_spec):
        cc = CompiledContract.from_spec(minimal_spec)
        assert cc.tool_blocklist_patterns == []
        assert cc.must_state_rules == []
        assert cc.must_precede_rules == []
        assert cc.context_budget_limit is None
        assert cc.judge_predicates == []

    def test_tool_blocklist_compile(self):
        spec = ContractSpecExtended(
            dsl_version="0.4",
            contractspec="1.0",
            kind="agent",
            name="blocklist-test",
            description="test",
            version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    tool_blocklist=[
                        ToolBlocklist(tools=["rm -rf /*", "curl|bash", "mkfs.*"])
                    ]
                )
            ),
        )
        cc = CompiledContract.from_spec(spec)
        assert len(cc.tool_blocklist_patterns) == 4  # 1 + 2 alternates + 1

    def test_blocklist_pattern_matches(self):
        spec = ContractSpecExtended(
            dsl_version="0.4",
            contractspec="1.0",
            kind="agent",
            name="blocklist-test",
            description="test",
            version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    tool_blocklist=[ToolBlocklist(tools=["rm"])]
                )
            ),
        )
        cc = CompiledContract.from_spec(spec)
        assert len(cc.tool_blocklist_patterns) == 1
        pattern = cc.tool_blocklist_patterns[0]
        assert pattern.match("rm") is not None
        assert pattern.match("Read") is None

    def test_blocklist_wildcard_match(self):
        spec = ContractSpecExtended(
            dsl_version="0.4",
            contractspec="1.0",
            kind="agent",
            name="wildcard-test",
            description="test",
            version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    tool_blocklist=[ToolBlocklist(tools=["tap_*"])]
                )
            ),
        )
        cc = CompiledContract.from_spec(spec)
        pattern = cc.tool_blocklist_patterns[0]
        assert pattern.search("tap_deepseek") is not None
        assert pattern.search("mcp__hermes") is None

    def test_blocklist_case_insensitive(self):
        spec = ContractSpecExtended(
            dsl_version="0.4",
            contractspec="1.0",
            kind="agent",
            name="case-test",
            description="test",
            version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    tool_blocklist=[ToolBlocklist(tools=["Rm"])]
                )
            ),
        )
        cc = CompiledContract.from_spec(spec)
        pattern = cc.tool_blocklist_patterns[0]
        assert pattern.match("rm") is not None
        assert pattern.match("RM") is not None
        assert pattern.match("Rm") is not None

    def test_allowlist_compile(self):
        spec = ContractSpecExtended(
            dsl_version="0.4",
            contractspec="1.0",
            kind="agent",
            name="allowlist-test",
            description="test",
            version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    tool_allowlist=[ToolAllowlist(tools=["Read", "Write", "Edit"])]
                )
            ),
        )
        cc = CompiledContract.from_spec(spec)
        assert len(cc.tool_allowlist_patterns) == 1
        scope, patterns = cc.tool_allowlist_patterns[0]
        assert scope == "session"
        assert len(patterns) == 3

    def test_must_state_compile(self):
        spec = ContractSpecExtended(
            dsl_version="0.4",
            contractspec="1.0",
            kind="agent",
            name="must-state-test",
            description="test",
            version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    must_state=[
                        MustState(
                            field="cost",
                            before_tool_pattern="tap_*|paid_api_*",
                            rationale="Cost required",
                        )
                    ]
                )
            ),
        )
        cc = CompiledContract.from_spec(spec)
        assert len(cc.must_state_rules) == 1
        rule = cc.must_state_rules[0]
        assert rule["field"] == "cost"
        assert len(rule["patterns"]) == 2
        assert rule["patterns"][0].search("tap_deepseek") is not None
        assert rule["patterns"][1].search("paid_api_anthropic") is not None

    def test_context_budget_compile(self):
        spec = ContractSpecExtended(
            dsl_version="0.4",
            contractspec="1.0",
            kind="agent",
            name="budget-test",
            description="test",
            version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    context_budget=ContextBudget(
                        max_tokens_per_turn=30000,
                        action_on_breach="deny",
                    )
                )
            ),
        )
        cc = CompiledContract.from_spec(spec)
        assert cc.context_budget_limit == 30000
        assert cc.context_budget_action == "deny"

    def test_must_precede_compile(self):
        spec = ContractSpecExtended(
            dsl_version="0.4",
            contractspec="1.0",
            kind="agent",
            name="precede-test",
            description="test",
            version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    must_precede=[
                        MustPrecede(before="challenge", after="recommendation", scope="turn")
                    ]
                )
            ),
        )
        cc = CompiledContract.from_spec(spec)
        assert len(cc.must_precede_rules) == 1
        assert cc.must_precede_rules[0]["before"] == "challenge"
        assert cc.must_precede_rules[0]["after"] == "recommendation"

    def test_process_drift_compile(self):
        spec = ContractSpecExtended(
            dsl_version="0.4",
            contractspec="1.0",
            kind="agent",
            name="drift-test",
            description="test",
            version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    process_drift=ProcessDrift(
                        window_size=20,
                        jsd_threshold=0.4,
                        action="warn",
                    )
                )
            ),
        )
        cc = CompiledContract.from_spec(spec)
        assert cc.process_drift_config is not None
        assert cc.process_drift_config.window_size == 20

    def test_judge_predicate_compile(self):
        spec = ContractSpecExtended(
            dsl_version="0.4",
            contractspec="1.0",
            kind="agent",
            name="judge-test",
            description="test",
            version="0.1",
            invariants=InvariantsExtended(
                process=ProcessInvariants(
                    judge_predicate=[
                        JudgePredicate(
                            rubric="Concrete recommendations only",
                            sample_rate=0.25,
                            model="ds-flash-free",
                            action_on_fail="theta_penalty",
                            cost_ceiling_usd_per_session=0.05,
                        )
                    ]
                )
            ),
        )
        cc = CompiledContract.from_spec(spec)
        assert len(cc.judge_predicates) == 1
        jp = cc.judge_predicates[0]
        assert jp["rubric"] == "Concrete recommendations only"
        assert jp["sample_rate"] == 0.25
        assert jp["model"] == "ds-flash-free"
