
from agentassert_typec_core.dsl.validator import validate_extended


class TestValidateExtended:
    def test_empty_contract_valid(self):
        data = {
            "dsl_version": "0.4",
            "contractspec": "1.0",
            "kind": "agent",
            "name": "test",
            "description": "test",
            "version": "0.1",
        }
        errors = validate_extended(data)
        assert errors == []

    def test_valid_tool_blocklist(self):
        data = {
            "invariants": {
                "process": [
                    {"tool_blocklist": {"tools": ["rm", "curl"], "scope": "session"}}
                ]
            }
        }
        errors = validate_extended(data)
        assert errors == []

    def test_blocklist_empty_tools(self):
        data = {
            "invariants": {
                "process": [
                    {"tool_blocklist": {"tools": [], "scope": "session"}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "BLOCKLIST_EMPTY_TOOLS" for e in errors)

    def test_blocklist_invalid_scope(self):
        data = {
            "invariants": {
                "process": [
                    {"tool_blocklist": {"tools": ["rm"], "scope": "bad_scope"}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "INVALID_SCOPE" for e in errors)

    def test_must_state_no_field(self):
        data = {
            "invariants": {
                "process": [
                    {"must_state": {"before_tool_pattern": "tap_*"}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "MUST_STATE_NO_FIELD" for e in errors)

    def test_must_state_no_pattern(self):
        data = {
            "invariants": {
                "process": [
                    {"must_state": {"field": "cost"}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "MUST_STATE_NO_PATTERN" for e in errors)

    def test_context_budget_invalid_max_tokens(self):
        data = {
            "invariants": {
                "process": [
                    {"context_budget": {"max_tokens_per_turn": 0}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "INVALID_CONTEXT_BUDGET" for e in errors)

    def test_context_budget_invalid_action(self):
        data = {
            "invariants": {
                "process": [
                    {"context_budget": {"max_tokens_per_turn": 1000, "action_on_breach": "explode"}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "INVALID_ACTION" for e in errors)

    def test_judge_no_rubric(self):
        data = {
            "invariants": {
                "process": [
                    {"judge_predicate": {"sample_rate": 0.2}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "JUDGE_NO_RUBRIC" for e in errors)

    def test_judge_invalid_sample_rate(self):
        data = {
            "invariants": {
                "process": [
                    {"judge_predicate": {"rubric": "test", "sample_rate": 1.5}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "INVALID_SAMPLE_RATE" for e in errors)

    def test_judge_invalid_action(self):
        data = {
            "invariants": {
                "process": [
                    {"judge_predicate": {"rubric": "test", "sample_rate": 0.2, "action_on_fail": "panic"}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "INVALID_JUDGE_ACTION" for e in errors)

    def test_must_precede_no_before(self):
        data = {
            "invariants": {
                "process": [
                    {"must_precede": {"after": "recommendation"}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "MUST_PRECEDE_NO_BEFORE" for e in errors)

    def test_must_precede_no_after(self):
        data = {
            "invariants": {
                "process": [
                    {"must_precede": {"before": "challenge"}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "MUST_PRECEDE_NO_AFTER" for e in errors)

    def test_must_precede_invalid_scope(self):
        data = {
            "invariants": {
                "process": [
                    {"must_precede": {"before": "x", "after": "y", "scope": "lifetime"}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "INVALID_MUST_PRECEDE_SCOPE" for e in errors)

    def test_process_drift_invalid_jsd(self):
        data = {
            "invariants": {
                "process": [
                    {"process_drift": {"jsd_threshold": 1.5}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "INVALID_JSD_THRESHOLD" for e in errors)

    def test_process_drift_invalid_action(self):
        data = {
            "invariants": {
                "process": [
                    {"process_drift": {"action": "halt"}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "INVALID_DRIFT_ACTION" for e in errors)

    def test_allowlist_empty_tools(self):
        data = {
            "invariants": {
                "process": [
                    {"tool_allowlist": {"tools": []}}
                ]
            }
        }
        errors = validate_extended(data)
        assert any(e.code == "ALLOWLIST_EMPTY_TOOLS" for e in errors)

    def test_multiple_operators_in_one_entry(self):
        data = {
            "invariants": {
                "process": [
                    {
                        "tool_blocklist": {"tools": ["rm"]},
                        "context_budget": {"max_tokens_per_turn": 1000},
                    }
                ]
            }
        }
        errors = validate_extended(data)
        assert errors == []
