from pathlib import Path


from agentassert_typec_core.dsl.parser import parse_contract

FIXTURES = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "contracts"


class TestParseContract:
    def test_safety_minimal(self):
        result = parse_contract(FIXTURES / "safety-minimal.yaml")
        assert result.is_valid
        assert result.contract is not None
        assert result.contract.dsl_version == "0.4"
        assert result.contract.name == "safety-minimal"
        assert result.contract.invariants is not None
        assert result.contract.invariants.process is not None
        assert len(result.contract.invariants.process.tool_blocklist) == 1
        bl = result.contract.invariants.process.tool_blocklist[0]
        assert "rm -rf /*" in bl.tools
        assert "curl|bash" in bl.tools

    def test_full_governance(self):
        result = parse_contract(FIXTURES / "full-governance.yaml")
        assert result.is_valid
        assert result.contract is not None
        assert result.contract.name == "full-governance"
        proc = result.contract.invariants.process
        assert len(proc.tool_blocklist) == 1
        assert len(proc.tool_allowlist) == 1
        assert len(proc.must_state) == 1
        assert len(proc.must_precede) == 1
        assert proc.context_budget is not None
        assert proc.context_budget.max_tokens_per_turn == 60000
        assert proc.process_drift is not None
        assert len(proc.judge_predicate) == 1

    def test_abc_v03_compat(self):
        result = parse_contract(FIXTURES / "abc-v03-compat.yaml")
        assert result.is_valid
        assert result.contract is not None
        assert result.contract.dsl_version == "0.3"
        assert result.contract.name == "abc-style"
        assert len(result.contract.invariants.hard) == 1
        assert len(result.contract.invariants.soft) == 1
        assert result.contract.invariants.process is None

    def test_missing_dsl_version_defaults(self):
        result = parse_contract(FIXTURES / "missing-dsl-version.yaml")
        assert result.is_valid
        assert result.contract is not None
        assert result.contract.dsl_version == "0.3"
        assert any(e.code == "MISSING_DSL_VERSION" for e in result.errors)

    def test_invalid_missing_name(self):
        result = parse_contract(FIXTURES / "invalid-missing-name.yaml")
        assert not result.is_valid
        assert result.contract is None

    def test_file_not_found(self):
        result = parse_contract("/nonexistent/path.yaml")
        assert not result.is_valid
        assert any(e.code == "FILE_NOT_FOUND" for e in result.errors)

    def test_invalid_yaml_raises(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text(": invalid: yaml: :")
        result = parse_contract(bad)
        assert not result.is_valid
        assert any(e.code == "YAML_PARSE_ERROR" for e in result.errors)

    def test_not_a_mapping(self, tmp_path):
        bad = tmp_path / "list.yaml"
        bad.write_text("- item1\n- item2\n")
        result = parse_contract(bad)
        assert not result.is_valid
        assert any(e.code == "NOT_A_MAPPING" for e in result.errors)
