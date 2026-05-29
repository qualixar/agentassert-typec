"""Phase 2 persistence tests — 15 tests minimum.

Tests cover:
- SessionStore open/put/get/flush/close lifecycle
- Write-behind semantics (put() does not write immediately)
- Serializers roundtrip for all 4 sub-systems
- monitor.attach_store + state survives restart (THE critical test)
- No-persist mode backward compat
- Session-ID isolation
- Concurrent evaluate safety
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
import threading
import time
from collections import defaultdict, deque
from pathlib import Path

import pytest

from agentassert_typec_core.models.contract import ContractSpecExtended
from agentassert_typec_core.monitor.session import SessionMonitor
from agentassert_typec_core.monitor.drift import DriftTracker
from agentassert_typec_core.monitor.theta import ThetaScorer
from agentassert_typec_core.monitor.violation_log import ViolationLog
from agentassert_typec_core.persistence.sqlite_store import SessionStore
from agentassert_typec_core.persistence.serializers import (
    dump_theta, load_theta,
    dump_drift, load_drift,
    dump_violations, load_violations,
    dump_meta, load_meta,
)
from agentassert_typec_core.models.events import PreAction, TurnEnd


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_session.db")


@pytest.fixture
def store(db_path):
    s = SessionStore(db_path)
    s.open()
    yield s
    try:
        s.close()
    except Exception:
        pass


def _make_minimal_contract() -> ContractSpecExtended:
    return ContractSpecExtended(
        dsl_version="0.4",
        contractspec="typec/v0.4",
        kind="agent",
        name="test-contract",
        description="test",
        version="0.1.0",
    )


def _make_monitor() -> SessionMonitor:
    return SessionMonitor(_make_minimal_contract())


# ---------------------------------------------------------------------------
# [1] SessionStore: open creates DB file
# ---------------------------------------------------------------------------

def test_store_open_creates_db_file(db_path):
    s = SessionStore(db_path)
    assert not os.path.exists(db_path)
    s.open()
    assert os.path.exists(db_path)
    s.close()


# ---------------------------------------------------------------------------
# [2] SessionStore: put/get roundtrip (after flush)
# ---------------------------------------------------------------------------

def test_store_put_get_roundtrip(store):
    store.put("key1", {"hello": "world", "num": 42})
    store.flush()
    result = store.get("key1")
    assert result == {"hello": "world", "num": 42}


# ---------------------------------------------------------------------------
# [3] SessionStore: missing key returns None
# ---------------------------------------------------------------------------

def test_store_get_missing_key_returns_none(store):
    assert store.get("nonexistent_key") is None


# ---------------------------------------------------------------------------
# [4] SessionStore: flush writes to disk (verify via independent connection)
# ---------------------------------------------------------------------------

def test_store_flush_writes_to_disk(db_path, store):
    store.put("check_key", {"value": 99})
    store.flush()

    # Open a fresh connection to same file and verify data is there
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT value FROM session_state WHERE key = ?", ("check_key",))
    row = cur.fetchone()
    conn.close()

    import json
    assert row is not None
    assert json.loads(row[0]) == {"value": 99}


# ---------------------------------------------------------------------------
# [5] SessionStore: write-behind — after put() before flush(), disk unchanged
# ---------------------------------------------------------------------------

def test_store_write_behind_not_immediate(db_path, store):
    # First flush to establish table
    store.flush()

    store.put("wb_key", {"x": 1})
    # Do NOT call flush yet — read directly from DB
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT value FROM session_state WHERE key = ?", ("wb_key",))
    row = cur.fetchone()
    conn.close()
    # Should not be there yet
    assert row is None


# ---------------------------------------------------------------------------
# [6] SessionStore: close() flushes
# ---------------------------------------------------------------------------

def test_store_close_flushes(db_path):
    s = SessionStore(db_path)
    s.open()
    s.put("close_key", {"data": "present"})
    s.close()

    import json
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT value FROM session_state WHERE key = ?", ("close_key",))
    row = cur.fetchone()
    conn.close()
    assert row is not None
    assert json.loads(row[0]) == {"data": "present"}


# ---------------------------------------------------------------------------
# [7] Serializer: ThetaScorer roundtrip
# ---------------------------------------------------------------------------

def test_serializer_theta_roundtrip():
    theta = ThetaScorer()
    theta.record_compliance(0.9, 0.8)
    theta.record_drift(0.15)
    theta.record_violation()
    theta.apply_penalty(0.05)

    data = dump_theta(theta)

    theta2 = ThetaScorer()
    load_theta(theta2, data)

    assert theta2._compliance_scores == theta._compliance_scores
    assert theta2._drift_scores == theta._drift_scores
    assert theta2._violation_count == theta._violation_count
    assert abs(theta2._penalty_sum - theta._penalty_sum) < 1e-9


# ---------------------------------------------------------------------------
# [8] Serializer: DriftTracker roundtrip
# ---------------------------------------------------------------------------

def test_serializer_drift_roundtrip():
    drift = DriftTracker(window=10)
    for tool in ["read_file", "bash", "read_file", "write_file", "bash"] * 2:
        drift.update(tool)

    data = dump_drift(drift)

    drift2 = DriftTracker(window=10)
    load_drift(drift2, data)

    assert list(drift2._call_sequence) == list(drift._call_sequence)
    assert drift2._total_updates == drift._total_updates
    # baseline may be None if < window updates
    if drift._baseline_counts is None:
        assert drift2._baseline_counts is None
    else:
        assert dict(drift2._baseline_counts) == dict(drift._baseline_counts)


# ---------------------------------------------------------------------------
# [9] Serializer: ViolationLog roundtrip
# ---------------------------------------------------------------------------

def test_serializer_violations_roundtrip():
    log = ViolationLog()
    log.record("tool_blocklist", "PreAction", "bash", "blocked")
    log.record_soft("pii_filter", "PostAction", "response", "email found")

    data = dump_violations(log)
    assert len(data) == 2

    log2 = ViolationLog()
    load_violations(log2, data)

    violations = log2.all_violations()
    assert len(violations) == 2
    assert violations[0]["name"] == "tool_blocklist"
    assert violations[1]["name"] == "pii_filter"


# ---------------------------------------------------------------------------
# [10] Serializer: SessionMonitor meta roundtrip
# ---------------------------------------------------------------------------

def test_serializer_meta_roundtrip():
    monitor = _make_monitor()
    monitor._turn_count = 7
    monitor._deny_count = 3
    monitor._seen_tools_session = {"bash", "read_file", "write_file"}

    data = dump_meta(monitor)

    monitor2 = _make_monitor()
    load_meta(monitor2, data)

    assert monitor2._turn_count == 7
    assert monitor2._deny_count == 3
    assert monitor2._seen_tools_session == {"bash", "read_file", "write_file"}
    # _seen_tools_turn must NOT be restored
    assert monitor2._seen_tools_turn == set()


# ---------------------------------------------------------------------------
# [11] monitor.attach_store loads state
# ---------------------------------------------------------------------------

def test_monitor_attach_store_loads_state(db_path):
    # First monitor: record some state
    monitor1 = _make_monitor()
    store1 = SessionStore(db_path)
    store1.open()
    monitor1.attach_store(store1)

    monitor1._violations.record("tool_blocklist", "PreAction", "bash", "blocked")
    monitor1._turn_count = 5
    monitor1._deny_count = 2
    monitor1._seen_tools_session.add("bash")
    monitor1.close()  # flushes + closes store

    # Second monitor: attach same DB
    monitor2 = _make_monitor()
    store2 = SessionStore(db_path)
    store2.open()
    monitor2.attach_store(store2)

    assert monitor2._turn_count == 5
    assert monitor2._deny_count == 2
    assert "bash" in monitor2._seen_tools_session
    violations = monitor2._violations.all_violations()
    assert len(violations) == 1
    assert violations[0]["name"] == "tool_blocklist"

    monitor2.close()


# ---------------------------------------------------------------------------
# [12] THE CRITICAL TEST: monitor state survives restart
# ---------------------------------------------------------------------------

def test_monitor_state_survives_restart(db_path):
    """Full lifecycle: create → add violations → close → new monitor with same DB → verify."""
    # Session 1
    monitor1 = _make_monitor()
    store1 = SessionStore(db_path)
    store1.open()
    monitor1.attach_store(store1)

    # Simulate some actions
    event1 = PreAction(session_id="s1", contract_id="test-contract", tool="bash", args={})
    monitor1._violations.record("tool_blocklist", "PreAction", "bash", "bash is blocked")
    monitor1._violations.record_soft("pii_filter", "PostAction", "response", "email found")
    monitor1._turn_count = 12
    monitor1._deny_count = 4
    monitor1._theta.record_compliance(0.85, 0.75)
    monitor1._theta.record_violation()

    monitor1.close()  # must flush everything

    # Session 2: fresh monitor, same DB file
    monitor2 = _make_monitor()
    store2 = SessionStore(db_path)
    store2.open()
    monitor2.attach_store(store2)

    # Verify all state restored
    assert monitor2._turn_count == 12
    assert monitor2._deny_count == 4
    violations = monitor2._violations.all_violations()
    assert len(violations) == 2

    names = {v["name"] for v in violations}
    assert "tool_blocklist" in names
    assert "pii_filter" in names

    # Theta scores must be preserved
    assert len(monitor2._theta._compliance_scores) == 1
    assert monitor2._theta._violation_count == 1

    monitor2.close()


# ---------------------------------------------------------------------------
# [13] --no-persist mode: monitor without store works identically
# ---------------------------------------------------------------------------

def test_monitor_no_persist_mode():
    monitor = _make_monitor()
    # No store attached — all operations must work
    monitor._violations.record("tool_blocklist", "PreAction", "bash", "blocked")
    monitor._turn_count = 3

    # evaluate() must work without store
    event = TurnEnd(session_id="s1", contract_id="test-contract", assistant_output="")
    result = monitor.evaluate(event)
    assert result is not None

    # close() must not raise
    se = monitor.close()
    assert se is not None


# ---------------------------------------------------------------------------
# [14] DB isolation by session_id
# ---------------------------------------------------------------------------

def test_db_isolation_by_session_id(tmp_path):
    from agentassert_typec_proxy.server import _resolve_db_path
    contract_path = str(tmp_path / "my-contract.yaml")

    db1 = _resolve_db_path(contract_path, session_id=None)
    db2 = _resolve_db_path(contract_path, session_id="agent1")
    db3 = _resolve_db_path(contract_path, session_id="agent2")

    assert db1 != db2
    assert db1 != db3
    assert db2 != db3
    assert "agent1" in db2
    assert "agent2" in db3


# ---------------------------------------------------------------------------
# [15] Concurrent evaluate: 10 threads, no corruption
# ---------------------------------------------------------------------------

def test_concurrent_evaluate_no_corruption(db_path):
    monitor = _make_monitor()
    store = SessionStore(db_path)
    store.open()
    monitor.attach_store(store)

    errors = []
    results = []

    def worker():
        try:
            event = TurnEnd(session_id="s1", contract_id="test-contract", assistant_output="")
            result = monitor.evaluate(event)
            results.append(result)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert errors == [], f"Errors during concurrent evaluate: {errors}"
    assert len(results) == 10
    monitor.close()
