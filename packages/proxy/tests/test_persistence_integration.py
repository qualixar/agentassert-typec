"""Phase 2 proxy integration persistence tests — 3 tests.

Tests:
- test_proxy_restart_preserves_theta
- test_proxy_restart_preserves_violations
- test_health_shows_persistence_info
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from agentassert_typec_core.monitor.session import SessionMonitor
from agentassert_typec_core.persistence.sqlite_store import SessionStore
from agentassert_typec_proxy.server import create_app, _resolve_db_path
from agentassert_typec_proxy.hot_reload import ContractWatcher

FIXTURES = Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "contracts"

_MINIMAL_CONTRACT = """
dsl_version: '0.4'
contractspec: 'typec/v0.4'
kind: agent
name: test-persist
description: test
version: '0.1.0'
"""


def _write_contract(tmp_path: Path) -> Path:
    c = tmp_path / "test-persist.yaml"
    c.write_text(_MINIMAL_CONTRACT)
    return c


def _make_client_app(contract_path: str, db_path: str | None = None):
    """Create an app with persistence backed to a specific db_path."""
    app = create_app(contract_path, persist=True)
    return app


# ---------------------------------------------------------------------------
# test_proxy_restart_preserves_theta
# ---------------------------------------------------------------------------

def test_proxy_restart_preserves_theta(tmp_path):
    """Create monitor, record theta state, close, reopen with same DB — theta is preserved."""
    contract = _write_contract(tmp_path)
    db_path = str(tmp_path / "theta-session.db")

    # Session 1
    monitor1 = SessionMonitor.from_yaml(str(contract))
    store1 = SessionStore(db_path)
    store1.open()
    monitor1.attach_store(store1)

    # Record some theta signals
    monitor1._theta.record_compliance(0.9, 0.85)
    monitor1._theta.record_compliance(0.8, 0.75)
    monitor1._theta.record_drift(0.1)
    monitor1._theta.apply_penalty(0.02)
    theta_before = monitor1._theta.compute()
    monitor1.close()

    # Session 2 — new monitor, same DB
    monitor2 = SessionMonitor.from_yaml(str(contract))
    store2 = SessionStore(db_path)
    store2.open()
    monitor2.attach_store(store2)

    theta_after = monitor2._theta.compute()
    assert abs(theta_before - theta_after) < 1e-6, (
        f"Theta not preserved: before={theta_before:.6f}, after={theta_after:.6f}"
    )
    monitor2.close()


# ---------------------------------------------------------------------------
# test_proxy_restart_preserves_violations
# ---------------------------------------------------------------------------

def test_proxy_restart_preserves_violations(tmp_path):
    """Violations accumulated before restart appear in monitor after restart."""
    contract = _write_contract(tmp_path)
    db_path = str(tmp_path / "violations-session.db")

    # Session 1
    monitor1 = SessionMonitor.from_yaml(str(contract))
    store1 = SessionStore(db_path)
    store1.open()
    monitor1.attach_store(store1)

    monitor1._violations.record("tool_blocklist", "PreAction", "bash", "blocked")
    monitor1._violations.record("tool_blocklist", "PreAction", "rm", "blocked")
    monitor1._violations.record_soft("pii_filter", "PostAction", "response", "email found")
    monitor1._turn_count = 10
    monitor1._deny_count = 2
    monitor1.close()

    # Session 2
    monitor2 = SessionMonitor.from_yaml(str(contract))
    store2 = SessionStore(db_path)
    store2.open()
    monitor2.attach_store(store2)

    violations = monitor2._violations.all_violations()
    assert len(violations) == 3
    assert monitor2._turn_count == 10
    assert monitor2._deny_count == 2

    names = [v["name"] for v in violations]
    assert names.count("tool_blocklist") == 2
    assert names.count("pii_filter") == 1

    monitor2.close()


# ---------------------------------------------------------------------------
# test_health_shows_persistence_info
# ---------------------------------------------------------------------------

def test_health_shows_persistence_info(tmp_path):
    """The /health endpoint returns persistence.enabled and persistence.db_path."""
    import asyncio
    from httpx import ASGITransport, AsyncClient

    contract = _write_contract(tmp_path)
    db_path = str(tmp_path / "health-test.db")

    # Manually wire a monitor + store into app state (same pattern as other proxy tests)
    async def _run():
        app = create_app(str(contract), persist=False)  # no lifespan store
        monitor = SessionMonitor.from_yaml(str(contract))

        # Attach store manually
        store = SessionStore(db_path)
        store.open()
        monitor.attach_store(store)

        app.state.monitor = monitor
        app.state.upstream_overrides = None
        app.state.db_path = db_path
        app.state.store = store
        app.state.watcher = ContractWatcher(str(contract))
        app.state.watcher.set_monitor(monitor)

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
            headers={"accept-encoding": "identity"},
        ) as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert "persistence" in data
            p = data["persistence"]
            assert p["enabled"] is True
            assert p["db_path"] is not None
            assert p["db_path"].endswith(".db")
            assert "dirty" in p

        monitor.close()

    asyncio.run(_run())

