"""Tests for tool_allowlist, must_precede, and TurnEnd enforcement — Phase 1 fixes."""
from __future__ import annotations

import pytest

from agentassert_typec_core.models.contract import (
    ContractSpecExtended,
    InvariantsExtended,
    ProcessInvariants,
    ToolAllowlist,
    MustPrecede,
)
from agentassert_typec_core.models.decisions import TypeCDecision
from agentassert_typec_core.models.events import PreAction, TurnEnd
from agentassert_typec_core.monitor.session import SessionMonitor


def _make_monitor(invariants_data: dict) -> SessionMonitor:
    contract = ContractSpecExtended(
        contractspec="1.0",
        kind="agent",
        name="test",
        description="test",
        version="0.1",
        invariants=InvariantsExtended(
            process=ProcessInvariants(**invariants_data)
        ),
    )
    return SessionMonitor(contract)


class TestToolAllowlist:
    def test_allowed_tool_passes(self):
        monitor = _make_monitor({"tool_allowlist": [ToolAllowlist(tools=["read_file", "write_file"])]})
        event = PreAction(session_id="s", contract_id="test", tool="read_file")
        result = monitor.evaluate(event)
        assert result.decision == TypeCDecision.ALLOW

    def test_wildcard_allowed(self):
        monitor = _make_monitor({"tool_allowlist": [ToolAllowlist(tools=["bash_*"])]})
        event = PreAction(session_id="s", contract_id="test", tool="bash_run")
        result = monitor.evaluate(event)
        assert result.decision == TypeCDecision.ALLOW

    def test_blocked_tool_denied(self):
        monitor = _make_monitor({"tool_allowlist": [ToolAllowlist(tools=["read_file"])]})
        event = PreAction(session_id="s", contract_id="test", tool="bash_run")
        result = monitor.evaluate(event)
        assert result.decision == TypeCDecision.DENY
        assert "tool_allowlist" in result.violation_name

    def test_empty_allowlist_allows_all(self):
        monitor = _make_monitor({})
        event = PreAction(session_id="s", contract_id="test", tool="anything")
        result = monitor.evaluate(event)
        assert result.decision == TypeCDecision.ALLOW

    def test_multi_block_union_allows(self):
        monitor = _make_monitor({
            "tool_allowlist": [
                ToolAllowlist(tools=["read_file"]),
                ToolAllowlist(tools=["write_file"]),
            ]
        })
        for tool in ("read_file", "write_file"):
            result = monitor.evaluate(PreAction(session_id="s", contract_id="test", tool=tool))
            assert result.decision == TypeCDecision.ALLOW

    def test_multi_block_blocked_if_in_none(self):
        monitor = _make_monitor({
            "tool_allowlist": [
                ToolAllowlist(tools=["read_file"]),
                ToolAllowlist(tools=["write_file"]),
            ]
        })
        result = monitor.evaluate(PreAction(session_id="s", contract_id="test", tool="bash"))
        assert result.decision == TypeCDecision.DENY


class TestMustPrecede:
    def test_correct_order_passes(self):
        monitor = _make_monitor({
            "must_precede": [MustPrecede(before="plan", after="execute")]
        })
        monitor.evaluate(PreAction(session_id="s", contract_id="test", tool="plan"))
        result = monitor.evaluate(PreAction(session_id="s", contract_id="test", tool="execute"))
        assert result.decision == TypeCDecision.ALLOW

    def test_wrong_order_denied(self):
        monitor = _make_monitor({
            "must_precede": [MustPrecede(before="plan", after="execute")]
        })
        result = monitor.evaluate(PreAction(session_id="s", contract_id="test", tool="execute"))
        assert result.decision == TypeCDecision.DENY
        assert "must_precede" in result.violation_name

    def test_unrelated_tool_not_blocked(self):
        monitor = _make_monitor({
            "must_precede": [MustPrecede(before="plan", after="execute")]
        })
        result = monitor.evaluate(PreAction(session_id="s", contract_id="test", tool="read_file"))
        assert result.decision == TypeCDecision.ALLOW

    def test_turn_scope_resets_on_turn_end(self):
        monitor = _make_monitor({
            "must_precede": [MustPrecede(before="plan", after="execute", scope="turn")]
        })
        monitor.evaluate(PreAction(session_id="s", contract_id="test", tool="plan"))
        monitor.evaluate(PreAction(session_id="s", contract_id="test", tool="execute"))
        monitor.evaluate(TurnEnd(session_id="s", contract_id="test", assistant_output=""))
        result = monitor.evaluate(PreAction(session_id="s", contract_id="test", tool="execute"))
        assert result.decision == TypeCDecision.DENY

    def test_session_scope_persists_across_turns(self):
        monitor = _make_monitor({
            "must_precede": [MustPrecede(before="plan", after="execute", scope="session")]
        })
        monitor.evaluate(PreAction(session_id="s", contract_id="test", tool="plan"))
        monitor.evaluate(TurnEnd(session_id="s", contract_id="test", assistant_output=""))
        result = monitor.evaluate(PreAction(session_id="s", contract_id="test", tool="execute"))
        assert result.decision == TypeCDecision.ALLOW


class TestTurnEndSeenToolsReset:
    def test_seen_tools_turn_cleared_on_turn_end(self):
        monitor = _make_monitor({
            "must_precede": [MustPrecede(before="plan", after="execute", scope="turn")]
        })
        monitor.evaluate(PreAction(session_id="s", contract_id="test", tool="plan"))
        assert "plan" in monitor._seen_tools_turn
        monitor.evaluate(TurnEnd(session_id="s", contract_id="test", assistant_output=""))
        assert "plan" not in monitor._seen_tools_turn

    def test_seen_tools_session_not_cleared_on_turn_end(self):
        monitor = _make_monitor({})
        monitor.evaluate(PreAction(session_id="s", contract_id="test", tool="read_file"))
        monitor.evaluate(TurnEnd(session_id="s", contract_id="test", assistant_output=""))
        assert "read_file" in monitor._seen_tools_session
