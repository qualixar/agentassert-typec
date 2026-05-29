"""Phase 3 repetition_guard tests — 10 tests minimum."""
from __future__ import annotations

import hashlib
from collections import deque, defaultdict

import pytest

from agentassert_typec_core.evaluator.content_eval import evaluate_repetition_guard
from agentassert_typec_core.models.contract import (
    ContractSpecExtended,
    ProcessInvariants,
    InvariantsExtended,
    RepetitionGuard,
)
from agentassert_typec_core.models.decisions import TypeCDecision
from agentassert_typec_core.models.events import PreAction
from agentassert_typec_core.monitor.session import SessionMonitor
from agentassert_typec_core.monitor.violation_log import ViolationLog
from agentassert_typec_core.dsl.ast_compiler import CompiledContract
from agentassert_typec_core.persistence.sqlite_store import SessionStore


def _make_compiled(
    window_size: int = 3,
    max_repeats: int = 2,
    action: str = "deny",
    ignore_tools: list[str] | None = None,
) -> CompiledContract:
    guard = RepetitionGuard(
        window_size=window_size,
        max_repeats=max_repeats,
        action=action,
        ignore_tools=ignore_tools or [],
    )
    proc = ProcessInvariants(repetition_guard=guard)
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


def _make_compiled_no_guard() -> CompiledContract:
    spec = ContractSpecExtended(
        dsl_version="0.4",
        contractspec="typec/v0.4",
        kind="agent",
        name="test",
        description="test",
        version="0.1.0",
    )
    return CompiledContract.from_spec(spec)


def _pre(tool: str) -> PreAction:
    return PreAction(session_id="s1", contract_id="test", tool=tool, args={})


def _make_history(*tools: str) -> deque:
    return deque(tools, maxlen=1000)


def _build_hash_counts(history: deque, W: int) -> defaultdict:
    counts: defaultdict[str, int] = defaultdict(int)
    hist = list(history)
    for i in range(W, len(hist) + 1):
        window = tuple(hist[i - W:i])
        key = hashlib.md5("|".join(window).encode()).hexdigest()
        counts[key] += 1
    return counts


# ---------------------------------------------------------------------------
# [1] No repetition — random tool calls always pass
# ---------------------------------------------------------------------------

def test_no_repetition_passes():
    compiled = _make_compiled(window_size=3, max_repeats=2)
    violations = ViolationLog()
    history = _make_history("read_file", "bash", "write_file")
    counts = _build_hash_counts(history, 3)
    result = evaluate_repetition_guard(_pre("list_dir"), compiled, history, counts, violations)
    assert result is None


# ---------------------------------------------------------------------------
# [2] Exact repeat triggers — same sequence max_repeats+1 times → DENY
# ---------------------------------------------------------------------------

def test_exact_repeat_triggers():
    compiled = _make_compiled(window_size=2, max_repeats=2, action="deny")
    violations = ViolationLog()

    # Build history: 2 complete windows of [bash, bash]
    # After this, seq_key count = 2 (max_repeats)
    # Next call of "bash" would be count 3 → trigger
    history = _make_history("bash", "bash", "bash", "bash")
    counts = _build_hash_counts(history, 2)

    # Now try [bash, bash] again — count goes to 3 > 2
    result = evaluate_repetition_guard(_pre("bash"), compiled, history, counts, violations)
    # "bash" appended to history → window = (bash, bash) → count already >= max_repeats
    assert result is not None
    assert result.decision == TypeCDecision.DENY


# ---------------------------------------------------------------------------
# [3] max_repeats boundary — exactly at boundary allows, one over denies
# ---------------------------------------------------------------------------

def test_max_repeats_boundary():
    """max_repeats=2: allowing up to 2 times. 3rd occurrence triggers DENY."""
    compiled = _make_compiled(window_size=2, max_repeats=2, action="deny")
    violations = ViolationLog()

    # Build a history where ["x","y"] window has been seen exactly max_repeats times.
    # history = [x,y,x,y] → windows: (x,y),(y,x),(x,y) → ("x","y") seen 2 times in hash_counts
    history = _make_history("x", "y", "x", "y")
    counts = _build_hash_counts(history, 2)
    # Verify setup: (x,y) has been counted 2 times
    seq_key_xy = hashlib.md5("x|y".encode()).hexdigest()
    assert counts[seq_key_xy] == 2

    # Next "y" call: candidate = [x,y,x,y,y] → last 2 = (y,y) → different sequence, allow
    result_y = evaluate_repetition_guard(_pre("y"), compiled, history, counts, violations)
    assert result_y is None  # (y,y) has count 0+1 = 1, ≤ max_repeats

    # Next "y" call where (x,y) is the window: candidate = [x,y,x,y,x,y] → (x,y) count = 2+1=3 > 2
    history2 = _make_history("x", "y", "x", "y", "x")
    counts2 = _build_hash_counts(history2, 2)
    result_deny = evaluate_repetition_guard(_pre("y"), compiled, history2, counts2, violations)
    assert result_deny is not None
    assert result_deny.decision == TypeCDecision.DENY


# ---------------------------------------------------------------------------
# [4] Different sequences don't trigger
# ---------------------------------------------------------------------------

def test_different_sequences_pass():
    compiled = _make_compiled(window_size=2, max_repeats=2)
    violations = ViolationLog()
    # No repeated patterns
    history = _make_history("read_file", "bash", "write_file", "list_dir")
    counts = _build_hash_counts(history, 2)
    result = evaluate_repetition_guard(_pre("read_file"), compiled, history, counts, violations)
    assert result is None


# ---------------------------------------------------------------------------
# [5] Ignored tool not counted
# ---------------------------------------------------------------------------

def test_ignored_tool_not_counted():
    compiled = _make_compiled(window_size=2, max_repeats=2, ignore_tools=["read_file"])
    violations = ViolationLog()
    # Even with lots of history, read_file is ignored
    history = _make_history("read_file", "read_file", "read_file", "read_file")
    counts = _build_hash_counts(history, 2)
    result = evaluate_repetition_guard(_pre("read_file"), compiled, history, counts, violations)
    assert result is None  # read_file is in ignore_tools


# ---------------------------------------------------------------------------
# [6] window_size must be >= 2 (schema validation)
# ---------------------------------------------------------------------------

def test_window_size_1_not_allowed():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        RepetitionGuard(window_size=1, max_repeats=2)


# ---------------------------------------------------------------------------
# [7] action=warn → soft violation, None returned
# ---------------------------------------------------------------------------

def test_action_warn_not_deny():
    compiled = _make_compiled(window_size=2, max_repeats=2, action="warn")
    violations = ViolationLog()
    history = _make_history("bash", "bash", "bash", "bash")
    counts = _build_hash_counts(history, 2)
    result = evaluate_repetition_guard(_pre("bash"), compiled, history, counts, violations)
    # warn action: no deny, but soft violation recorded
    assert result is None
    v = violations.all_violations()
    assert len(v) == 1
    assert v[0]["kind"] == "soft"


# ---------------------------------------------------------------------------
# [8] Denied tool call not added to history
# ---------------------------------------------------------------------------

def test_history_not_updated_on_deny(tmp_path):
    """Monitor._commit_to_history is only called after an ALLOW result."""
    spec = ContractSpecExtended(
        dsl_version="0.4",
        contractspec="typec/v0.4",
        kind="agent",
        name="test",
        description="test",
        version="0.1.0",
        invariants=InvariantsExtended(
            process=ProcessInvariants(
                repetition_guard=RepetitionGuard(window_size=2, max_repeats=2, action="deny")
            )
        ),
    )
    monitor = SessionMonitor(spec)
    # Pre-load history to trigger repetition on next "bash"
    monitor._tool_call_history.extend(["bash", "bash", "bash", "bash"])
    window = tuple(["bash", "bash"])
    seq_key = hashlib.md5("|".join(window).encode()).hexdigest()
    monitor._sequence_hash_counts[seq_key] = 3  # already over max

    history_len_before = len(monitor._tool_call_history)
    event = PreAction(session_id="s1", contract_id="test", tool="bash", args={})
    result = monitor.evaluate(event)

    assert result.is_deny()
    # History must NOT grow because the call was denied
    assert len(monitor._tool_call_history) == history_len_before
    monitor.close()


# ---------------------------------------------------------------------------
# [9] New session starts fresh
# ---------------------------------------------------------------------------

def test_session_reset_clears_repetition():
    spec = ContractSpecExtended(
        dsl_version="0.4",
        contractspec="typec/v0.4",
        kind="agent",
        name="test",
        description="test",
        version="0.1.0",
        invariants=InvariantsExtended(
            process=ProcessInvariants(
                repetition_guard=RepetitionGuard(window_size=2, max_repeats=2, action="deny")
            )
        ),
    )
    monitor1 = SessionMonitor(spec)
    assert len(monitor1._tool_call_history) == 0
    assert len(monitor1._sequence_hash_counts) == 0

    monitor2 = SessionMonitor(spec)
    assert len(monitor2._tool_call_history) == 0
    assert len(monitor2._sequence_hash_counts) == 0
    monitor1.close()
    monitor2.close()


# ---------------------------------------------------------------------------
# [10] Repetition state persisted and loaded on restart
# ---------------------------------------------------------------------------

def test_repetition_persisted(tmp_path):
    db_path = str(tmp_path / "rep-session.db")
    spec = ContractSpecExtended(
        dsl_version="0.4",
        contractspec="typec/v0.4",
        kind="agent",
        name="test",
        description="test",
        version="0.1.0",
        invariants=InvariantsExtended(
            process=ProcessInvariants(
                repetition_guard=RepetitionGuard(window_size=2, max_repeats=2, action="deny")
            )
        ),
    )

    # Session 1
    monitor1 = SessionMonitor(spec)
    store1 = SessionStore(db_path)
    store1.open()
    monitor1.attach_store(store1)

    monitor1._tool_call_history.extend(["bash", "read_file", "bash"])
    monitor1._sequence_hash_counts["abc123"] = 5
    monitor1.close()

    # Session 2
    monitor2 = SessionMonitor(spec)
    store2 = SessionStore(db_path)
    store2.open()
    monitor2.attach_store(store2)

    assert list(monitor2._tool_call_history) == ["bash", "read_file", "bash"]
    assert monitor2._sequence_hash_counts["abc123"] == 5
    monitor2.close()
