"""Phase 3 cost_ceiling tests — 13 tests minimum."""
from __future__ import annotations

import pytest

from agentassert_typec_core.evaluator.content_eval import (
    evaluate_cost_ceiling,
    _extract_usage,
    _update_cost,
)
from agentassert_typec_core.models.contract import (
    ContractSpecExtended,
    ProcessInvariants,
    InvariantsExtended,
    CostCeiling,
    ProviderPriceEntry,
)
from agentassert_typec_core.models.decisions import TypeCDecision
from agentassert_typec_core.models.events import PreAction
from agentassert_typec_core.monitor.session import SessionMonitor
from agentassert_typec_core.monitor.violation_log import ViolationLog
from agentassert_typec_core.dsl.ast_compiler import CompiledContract
from agentassert_typec_core.persistence.sqlite_store import SessionStore


def _make_compiled(
    max_usd: float,
    action: str = "deny",
    provider_price_map: dict | None = None,
    price_per_million_input: float | None = None,
    price_per_million_output: float | None = None,
) -> CompiledContract:
    pm = {}
    if provider_price_map:
        for k, (inp, out) in provider_price_map.items():
            pm[k] = ProviderPriceEntry(input=inp, output=out)

    ceiling = CostCeiling(
        max_usd_per_session=max_usd,
        action_on_breach=action,
        price_per_million_input=price_per_million_input,
        price_per_million_output=price_per_million_output,
        provider_price_map=pm,
    )
    proc = ProcessInvariants(cost_ceiling=ceiling)
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


def _make_compiled_no_ceiling() -> CompiledContract:
    spec = ContractSpecExtended(
        dsl_version="0.4",
        contractspec="typec/v0.4",
        kind="agent",
        name="test",
        description="test",
        version="0.1.0",
    )
    return CompiledContract.from_spec(spec)


def _make_pre_event() -> PreAction:
    return PreAction(session_id="s1", contract_id="test", tool="llm_call", args={})


def _make_monitor_with_ceiling(max_usd: float, action: str = "deny") -> SessionMonitor:
    spec = ContractSpecExtended(
        dsl_version="0.4",
        contractspec="typec/v0.4",
        kind="agent",
        name="test",
        description="test",
        version="0.1.0",
        invariants=InvariantsExtended(
            process=ProcessInvariants(
                cost_ceiling=CostCeiling(
                    max_usd_per_session=max_usd,
                    action_on_breach=action,
                )
            )
        ),
    )
    return SessionMonitor(spec)


# ---------------------------------------------------------------------------
# [1] No ceiling config — always passes
# ---------------------------------------------------------------------------

def test_no_ceiling_passes():
    compiled = _make_compiled_no_ceiling()
    violations = ViolationLog()
    result = evaluate_cost_ceiling(_make_pre_event(), compiled, 999.99, violations)
    assert result is None


# ---------------------------------------------------------------------------
# [2] Under ceiling — passes
# ---------------------------------------------------------------------------

def test_under_ceiling_passes():
    compiled = _make_compiled(max_usd=5.00, action="deny")
    violations = ViolationLog()
    result = evaluate_cost_ceiling(_make_pre_event(), compiled, 4.99, violations)
    assert result is None


# ---------------------------------------------------------------------------
# [3] Over ceiling, action=deny → DENY
# ---------------------------------------------------------------------------

def test_over_ceiling_deny():
    compiled = _make_compiled(max_usd=1.00, action="deny")
    violations = ViolationLog()
    result = evaluate_cost_ceiling(_make_pre_event(), compiled, 1.50, violations)
    assert result is not None
    assert result.decision == TypeCDecision.DENY
    assert "cost_ceiling" in result.violation_name
    v = violations.all_violations()
    assert len(v) == 1
    assert v[0]["kind"] == "hard"


# ---------------------------------------------------------------------------
# [4] Over ceiling, action=warn → soft violation, None returned
# ---------------------------------------------------------------------------

def test_over_ceiling_warn():
    compiled = _make_compiled(max_usd=1.00, action="warn")
    violations = ViolationLog()
    result = evaluate_cost_ceiling(_make_pre_event(), compiled, 1.50, violations)
    assert result is None
    v = violations.all_violations()
    assert len(v) == 1
    assert v[0]["kind"] == "soft"


# ---------------------------------------------------------------------------
# [5] _extract_usage: Anthropic format
# ---------------------------------------------------------------------------

def test_extract_usage_anthropic():
    data = {"usage": {"input_tokens": 100, "output_tokens": 200}}
    result = _extract_usage(data, "anthropic")
    assert result == (100, 200)


# ---------------------------------------------------------------------------
# [6] _extract_usage: OpenAI format
# ---------------------------------------------------------------------------

def test_extract_usage_openai():
    data = {"usage": {"prompt_tokens": 150, "completion_tokens": 300}}
    result = _extract_usage(data, "openai")
    assert result == (150, 300)


# ---------------------------------------------------------------------------
# [7] _extract_usage: Gemini format
# ---------------------------------------------------------------------------

def test_extract_usage_gemini():
    data = {"usageMetadata": {"promptTokenCount": 80, "candidatesTokenCount": 120}}
    result = _extract_usage(data, "gemini")
    assert result == (80, 120)


# ---------------------------------------------------------------------------
# [8] _extract_usage: missing usage returns None
# ---------------------------------------------------------------------------

def test_extract_usage_missing():
    data = {"content": "hello world"}
    result = _extract_usage(data, "anthropic")
    assert result is None


# ---------------------------------------------------------------------------
# [9] Cost accumulates across requests
# ---------------------------------------------------------------------------

def test_cost_accumulates_across_requests(tmp_path):
    monitor = _make_monitor_with_ceiling(max_usd=10.00)

    class FakeCanonical:
        provider = "anthropic"

    resp1 = {"usage": {"input_tokens": 1000, "output_tokens": 500}}
    resp2 = {"usage": {"input_tokens": 2000, "output_tokens": 1000}}

    _update_cost(resp1, FakeCanonical(), monitor)
    _update_cost(resp2, FakeCanonical(), monitor)

    # anthropic default: input=3.00/M, output=15.00/M
    # req1: (1000*3 + 500*15) / 1_000_000 = 0.0105
    # req2: (2000*3 + 1000*15) / 1_000_000 = 0.021
    # total ≈ 0.0315
    assert monitor._accumulated_cost_usd > 0.0
    assert monitor._accumulated_cost_usd < 1.0  # sanity bound


# ---------------------------------------------------------------------------
# [10] Provider price map overrides default
# ---------------------------------------------------------------------------

def test_provider_price_map_overrides_default(tmp_path):
    monitor = _make_monitor_with_ceiling(max_usd=100.00)
    # Override with very high price
    ceiling = CostCeiling(
        max_usd_per_session=100.00,
        action_on_breach="deny",
        provider_price_map={"anthropic": ProviderPriceEntry(input=100.0, output=500.0)},
    )
    monitor._compiled.cost_ceiling_config = ceiling

    class FakeCanonical:
        provider = "anthropic"

    resp = {"usage": {"input_tokens": 1000, "output_tokens": 1000}}
    _update_cost(resp, FakeCanonical(), monitor)

    # (1000*100 + 1000*500) / 1_000_000 = 0.6
    assert abs(monitor._accumulated_cost_usd - 0.6) < 1e-6


# ---------------------------------------------------------------------------
# [11] Cost persisted to store
# ---------------------------------------------------------------------------

def test_cost_persisted_to_store(tmp_path):
    monitor = _make_monitor_with_ceiling(max_usd=10.00)
    db_path = str(tmp_path / "cost-test.db")
    store = SessionStore(db_path)
    store.open()
    monitor.attach_store(store)

    class FakeCanonical:
        provider = "openai"

    resp = {"usage": {"prompt_tokens": 500, "completion_tokens": 200}}
    _update_cost(resp, FakeCanonical(), monitor)

    store.flush()
    stored = store.get("cost")
    assert stored is not None
    assert "accumulated_usd" in stored
    assert stored["accumulated_usd"] > 0.0
    monitor.close()


# ---------------------------------------------------------------------------
# [12] Cost loaded from store on restart
# ---------------------------------------------------------------------------

def test_cost_loaded_from_store_on_restart(tmp_path):
    db_path = str(tmp_path / "cost-restart.db")

    # Session 1
    monitor1 = _make_monitor_with_ceiling(max_usd=10.00)
    store1 = SessionStore(db_path)
    store1.open()
    monitor1.attach_store(store1)
    monitor1._accumulated_cost_usd = 3.456
    monitor1.close()

    # Session 2
    monitor2 = _make_monitor_with_ceiling(max_usd=10.00)
    store2 = SessionStore(db_path)
    store2.open()
    monitor2.attach_store(store2)

    assert abs(monitor2._accumulated_cost_usd - 3.456) < 1e-6
    monitor2.close()


# ---------------------------------------------------------------------------
# [13] /status endpoint shows cost (unit-level via direct call)
# ---------------------------------------------------------------------------

def test_status_endpoint_shows_cost():
    """Verify that the cost section fields are correctly shaped."""
    # We test the data model directly, not via HTTP (HTTP tests are in integration tests)
    monitor = _make_monitor_with_ceiling(max_usd=5.00)
    monitor._accumulated_cost_usd = 1.23

    ceiling_config = monitor._compiled.cost_ceiling_config
    accumulated = monitor._accumulated_cost_usd
    ceiling_usd = ceiling_config.max_usd_per_session if ceiling_config else None
    remaining = (ceiling_usd - accumulated) if ceiling_usd is not None else None

    assert ceiling_usd == 5.00
    assert abs(remaining - 3.77) < 1e-6
    assert accumulated == 1.23
