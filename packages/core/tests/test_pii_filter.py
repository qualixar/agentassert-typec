"""Phase 3 pii_filter tests — 14 tests minimum."""
from __future__ import annotations

import re
import pytest

from agentassert_typec_core.evaluator.content_eval import (
    evaluate_pii_filter,
    _apply_pii_redaction,
)
from agentassert_typec_core.evaluator.pii_patterns import _PII_PATTERNS
from agentassert_typec_core.models.contract import (
    ContractSpecExtended,
    ProcessInvariants,
    InvariantsExtended,
    PiiFilter,
    PiiPatternGroup,
    CustomPiiPattern,
)
from agentassert_typec_core.models.decisions import TypeCDecision
from agentassert_typec_core.monitor.violation_log import ViolationLog
from agentassert_typec_core.dsl.ast_compiler import CompiledContract


def _make_compiled(
    patterns: list[PiiPatternGroup],
    action: str = "log",
    streaming_action: str = "log",
    custom_patterns: list | None = None,
) -> CompiledContract:
    pii_filter = PiiFilter(
        patterns=patterns,
        action=action,
        streaming_action=streaming_action,
        custom_patterns=custom_patterns or [],
    )
    proc = ProcessInvariants(pii_filter=pii_filter)
    invariants = InvariantsExtended(process=proc)
    spec = ContractSpecExtended(
        dsl_version="0.4",
        contractspec="typec/v0.4",
        kind="agent",
        name="test",
        description="test",
        version="0.1.0",
        invariants=invariants,
    )
    return CompiledContract.from_spec(spec)


def _make_compiled_no_pii() -> CompiledContract:
    spec = ContractSpecExtended(
        dsl_version="0.4",
        contractspec="typec/v0.4",
        kind="agent",
        name="test",
        description="test",
        version="0.1.0",
    )
    return CompiledContract.from_spec(spec)


# ---------------------------------------------------------------------------
# [1] Clean text passes — no PII
# ---------------------------------------------------------------------------

def test_no_pii_passes():
    compiled = _make_compiled([PiiPatternGroup.email])
    violations = ViolationLog()
    result = evaluate_pii_filter("Hello world, no PII here!", compiled, violations, False)
    assert result is None
    assert len(violations.all_violations()) == 0


# ---------------------------------------------------------------------------
# [2] Email detected
# ---------------------------------------------------------------------------

def test_email_detected():
    compiled = _make_compiled([PiiPatternGroup.email], action="block")
    violations = ViolationLog()
    result = evaluate_pii_filter("Contact: user@example.com", compiled, violations, False)
    assert result is not None
    assert result.is_deny()
    assert "pii_filter" in result.violation_name


# ---------------------------------------------------------------------------
# [3] Phone detected
# ---------------------------------------------------------------------------

def test_phone_detected():
    compiled = _make_compiled([PiiPatternGroup.phone], action="block")
    violations = ViolationLog()
    result = evaluate_pii_filter("+1 (555) 123-4567", compiled, violations, False)
    assert result is not None
    assert result.is_deny()


# ---------------------------------------------------------------------------
# [4] SSN detected
# ---------------------------------------------------------------------------

def test_ssn_detected():
    compiled = _make_compiled([PiiPatternGroup.ssn], action="block")
    violations = ViolationLog()
    result = evaluate_pii_filter("SSN: 123-45-6789", compiled, violations, False)
    assert result is not None
    assert result.is_deny()


# ---------------------------------------------------------------------------
# [5] Credit card detected
# ---------------------------------------------------------------------------

def test_credit_card_detected():
    compiled = _make_compiled([PiiPatternGroup.credit_card], action="block")
    violations = ViolationLog()
    # Visa number (16 digits, starts with 4)
    result = evaluate_pii_filter("Card: 4111111111111111", compiled, violations, False)
    assert result is not None
    assert result.is_deny()


# ---------------------------------------------------------------------------
# [6] API key detected
# ---------------------------------------------------------------------------

def test_api_key_detected():
    compiled = _make_compiled([PiiPatternGroup.api_key], action="block")
    violations = ViolationLog()
    # sk- followed by 20+ alphanumeric chars (no extra dashes in suffix)
    result = evaluate_pii_filter("My key: sk-AbCdEfGhIjKlMnOpQrStUvWx", compiled, violations, False)
    assert result is not None
    assert result.is_deny()


# ---------------------------------------------------------------------------
# [7] action=log does not deny
# ---------------------------------------------------------------------------

def test_action_log_does_not_deny():
    compiled = _make_compiled([PiiPatternGroup.email], action="log")
    violations = ViolationLog()
    result = evaluate_pii_filter("user@example.com", compiled, violations, False)
    assert result is None  # log does not return a result
    v = violations.all_violations()
    assert len(v) == 1
    assert v[0]["kind"] == "soft"


# ---------------------------------------------------------------------------
# [8] action=block returns DENY
# ---------------------------------------------------------------------------

def test_action_block_returns_deny():
    compiled = _make_compiled([PiiPatternGroup.email], action="block")
    violations = ViolationLog()
    result = evaluate_pii_filter("user@example.com", compiled, violations, False)
    assert result is not None
    assert result.decision == TypeCDecision.DENY


# ---------------------------------------------------------------------------
# [9] action=redact returns REDACT
# ---------------------------------------------------------------------------

def test_action_redact_returns_redact():
    compiled = _make_compiled([PiiPatternGroup.email], action="redact")
    violations = ViolationLog()
    result = evaluate_pii_filter("user@example.com", compiled, violations, False)
    assert result is not None
    assert result.decision == TypeCDecision.REDACT


# ---------------------------------------------------------------------------
# [10] _apply_pii_redaction replaces PII
# ---------------------------------------------------------------------------

def test_redact_replaces_pii():
    patterns = [("email", _PII_PATTERNS["email"])]
    text = "Contact: user@example.com and admin@corp.io"
    redacted = _apply_pii_redaction(text, patterns)
    assert "user@example.com" not in redacted
    assert "admin@corp.io" not in redacted
    assert "[REDACTED:EMAIL]" in redacted


# ---------------------------------------------------------------------------
# [11] streaming block degrades to warn
# ---------------------------------------------------------------------------

def test_streaming_block_degrades_to_warn():
    compiled = _make_compiled([PiiPatternGroup.email], action="block", streaming_action="warn")
    violations = ViolationLog()
    result = evaluate_pii_filter("user@example.com", compiled, violations, is_streaming=True)
    # Streaming with block action degrades to warn — no deny returned
    assert result is None
    v = violations.all_violations()
    assert len(v) == 1
    assert v[0]["kind"] == "soft"


# ---------------------------------------------------------------------------
# [12] Custom pattern detected
# ---------------------------------------------------------------------------

def test_custom_pattern():
    custom = [CustomPiiPattern(name="project_id", regex=r"PROJ-[0-9]{6}")]
    compiled = _make_compiled([], action="block", custom_patterns=custom)
    violations = ViolationLog()
    result = evaluate_pii_filter("Working on PROJ-123456", compiled, violations, False)
    assert result is not None
    assert result.is_deny()


# ---------------------------------------------------------------------------
# [13] Empty text passes
# ---------------------------------------------------------------------------

def test_empty_text_passes():
    compiled = _make_compiled([PiiPatternGroup.email], action="block")
    violations = ViolationLog()
    result = evaluate_pii_filter("", compiled, violations, False)
    assert result is None


# ---------------------------------------------------------------------------
# [14] Multiple PII types detected — both reported
# ---------------------------------------------------------------------------

def test_multiple_pii_types_detected():
    compiled = _make_compiled(
        [PiiPatternGroup.email, PiiPatternGroup.phone],
        action="log",
    )
    violations = ViolationLog()
    result = evaluate_pii_filter(
        "Email: user@example.com Phone: 555-123-4567",
        compiled, violations, False,
    )
    assert result is None  # log action
    v = violations.all_violations()
    assert len(v) == 1
    assert "email" in v[0]["reason"]
    assert "phone" in v[0]["reason"]
