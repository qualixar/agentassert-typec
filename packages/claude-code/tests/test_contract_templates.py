from pathlib import Path

from agentassert_typec_core.dsl.parser import parse_contract

TEMPLATES = Path(__file__).parent.parent / "src" / "agentassert_typec_claude_code" / "contracts" / "templates"


def test_safety_minimal_valid():
    result = parse_contract(TEMPLATES / "safety-minimal.yaml")
    assert result.is_valid


def test_partner_mode_valid():
    result = parse_contract(TEMPLATES / "partner-mode.yaml")
    assert result.is_valid


def test_full_governance_valid():
    result = parse_contract(TEMPLATES / "full-governance.yaml")
    assert result.is_valid
