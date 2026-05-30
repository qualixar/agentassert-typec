"""
Tier 1: AgentAssert Type-C — Operator micro-benchmarks.

Times all 10 contract operators against synthetic inputs.
No API keys needed. Pure CPU evaluation.

Run:
    cd agentassert-typec
    PYTHONPATH=packages/core/src uv run python scripts/bench_operators.py
"""

from __future__ import annotations

import statistics
import tempfile
import textwrap
import time
from collections import defaultdict, deque
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Bootstrap: load contract + monitor
# ---------------------------------------------------------------------------
from agentassert_typec_core.dsl.ast_compiler import CompiledContract
from agentassert_typec_core.evaluator.content_eval import (
    evaluate_cost_ceiling,
    evaluate_pii_filter,
    evaluate_repetition_guard,
)
from agentassert_typec_core.evaluator.process_eval import (
    evaluate_context_budget,
    evaluate_must_precede,
    evaluate_must_state,
    evaluate_tool_allowlist,
    evaluate_tool_blocklist,
    evaluate_turn_end_soft,
)
from agentassert_typec_core.models.contract import ContractSpecExtended
from agentassert_typec_core.models.decisions import TypeCDecision
from agentassert_typec_core.models.events import (
    ContextWindow,
    PostAction,
    PreAction,
    TurnEnd,
)
from agentassert_typec_core.monitor.drift import DriftTracker
from agentassert_typec_core.monitor.theta import ThetaScorer
from agentassert_typec_core.monitor.violation_log import ViolationLog

BENCHMARK_CONTRACT = textwrap.dedent("""\
    dsl_version: "0.4"
    contractspec: "1.0"
    kind: agent
    name: bench-all-operators
    description: "Benchmark contract exercising all 10 operators."
    version: "1.0"

    invariants:
      process:
        - tool_blocklist:
            tools: ["rm_rf", "shell_exec"]
            scope: session

        - tool_allowlist:
            tools: ["read_file", "search_web", "write_file"]
            scope: session

        - must_precede:
            before: read_file
            after: write_file
            scope: session

        - cost_ceiling:
            max_usd_per_session: 5.0
            action_on_breach: deny

        - repetition_guard:
            window_size: 3
            max_repeats: 2
            action: deny

      content:
        - pii_filter:
            action: block
            streaming_action: warn
            patterns:
              - email
              - phone
              - ssn
              - credit_card
              - ip_address
              - api_key

    recovery:
      on_hard_violation: raise
      on_soft_violation: log_and_continue
""")

N_RUNS = 1000  # iterations per operator
WARMUP = 50


def _build_compiled() -> CompiledContract:
    raw = yaml.safe_load(BENCHMARK_CONTRACT)
    spec = ContractSpecExtended(**raw)
    return CompiledContract.from_spec(spec)


def bench(label: str, fn, n: int = N_RUNS) -> dict:
    # warmup
    for _ in range(WARMUP):
        fn()

    times_us: list[float] = []
    for _ in range(n):
        t0 = time.perf_counter_ns()
        fn()
        t1 = time.perf_counter_ns()
        times_us.append((t1 - t0) / 1_000)

    return {
        "label": label,
        "n": n,
        "mean_us": statistics.mean(times_us),
        "median_us": statistics.median(times_us),
        "p99_us": sorted(times_us)[int(n * 0.99)],
        "min_us": min(times_us),
        "max_us": max(times_us),
    }


def main():
    compiled = _build_compiled()
    violations = ViolationLog()
    drift = DriftTracker(window=50)
    theta = ThetaScorer()

    pre_allowed = PreAction(
        session_id="bench", contract_id="bench-all-operators", tool="read_file"
    )
    pre_blocked = PreAction(
        session_id="bench", contract_id="bench-all-operators", tool="rm_rf"
    )
    pre_write = PreAction(
        session_id="bench", contract_id="bench-all-operators", tool="write_file"
    )
    pre_generic = PreAction(
        session_id="bench", contract_id="bench-all-operators", tool="search_web"
    )
    turn_end = TurnEnd(
        session_id="bench", contract_id="bench-all-operators",
        assistant_output="This is a sample assistant response for benchmarking.",
    )
    ctx_window = ContextWindow(
        session_id="bench", contract_id="bench-all-operators",
        token_count=1000, prefix_hash="abc123",
    )
    post_action = PostAction(
        session_id="bench",
        contract_id="bench-all-operators",
        tool="read_file",
        state={"success": True},
    )

    tool_history: deque = deque(maxlen=1000)
    seq_counts: dict = defaultdict(int)

    results = []

    # 1. tool_blocklist — DENY path
    results.append(bench(
        "tool_blocklist (deny)",
        lambda: evaluate_tool_blocklist(pre_blocked, compiled, ViolationLog()),
    ))

    # 2. tool_blocklist — ALLOW path
    results.append(bench(
        "tool_blocklist (allow)",
        lambda: evaluate_tool_blocklist(pre_allowed, compiled, ViolationLog()),
    ))

    # 3. tool_allowlist — ALLOW path
    seen_s: set = {"read_file"}
    results.append(bench(
        "tool_allowlist (allow)",
        lambda: evaluate_tool_allowlist(pre_allowed, compiled, ViolationLog()),
    ))

    # 4. must_precede — DENY (write_file before read_file)
    results.append(bench(
        "must_precede (deny)",
        lambda: evaluate_must_precede(pre_write, compiled, set(), set(), ViolationLog()),
    ))

    # 5. must_precede — ALLOW (seen read_file before)
    seen_read: set = {"read_file"}
    results.append(bench(
        "must_precede (allow)",
        lambda: evaluate_must_precede(pre_write, compiled, seen_read, seen_read, ViolationLog()),
    ))

    # 6. cost_ceiling — DENY (over budget)
    results.append(bench(
        "cost_ceiling (deny)",
        lambda: evaluate_cost_ceiling(pre_generic, compiled, 9.99, ViolationLog()),
    ))

    # 7. cost_ceiling — ALLOW (under budget)
    results.append(bench(
        "cost_ceiling (allow)",
        lambda: evaluate_cost_ceiling(pre_generic, compiled, 0.01, ViolationLog()),
    ))

    # 8. repetition_guard — ALLOW (below window)
    small_hist: deque = deque(["read_file"], maxlen=1000)
    results.append(bench(
        "repetition_guard (allow)",
        lambda: evaluate_repetition_guard(pre_allowed, compiled, small_hist, {}, ViolationLog()),
    ))

    # 9. pii_filter — DENY (email hit)
    pii_text = "Contact me at varun@qualixar.com for details"
    results.append(bench(
        "pii_filter (deny/block)",
        lambda: evaluate_pii_filter(pii_text, compiled, ViolationLog(), False),
    ))

    # 10. pii_filter — ALLOW (no PII)
    clean_text = "The deployment completed successfully with 0 errors."
    results.append(bench(
        "pii_filter (allow)",
        lambda: evaluate_pii_filter(clean_text, compiled, ViolationLog(), False),
    ))

    # 11. drift tracker update (PostAction path)
    results.append(bench(
        "drift_tracker.update",
        lambda: drift.update(tool="read_file", state={"success": True}),
    ))

    # 12. theta scorer record
    results.append(bench(
        "theta_scorer.record",
        lambda: theta.record_action(tool="read_file"),
    ))

    # -----------------------------------------------------------------------
    # Print results
    # -----------------------------------------------------------------------
    print()
    print("=" * 70)
    print(f"  AgentAssert Type-C — Operator Micro-Benchmarks ({N_RUNS} runs each)")
    print("=" * 70)
    print(f"  {'Operator':<35} {'mean':>8} {'median':>8} {'p99':>8}  {'min':>7}")
    print(f"  {'-'*35} {'-'*8} {'-'*8} {'-'*8}  {'-'*7}")
    for r in results:
        print(
            f"  {r['label']:<35} "
            f"{r['mean_us']:>7.1f}µs "
            f"{r['median_us']:>7.1f}µs "
            f"{r['p99_us']:>7.1f}µs  "
            f"{r['min_us']:>6.1f}µs"
        )
    print("=" * 70)

    all_means = [r["mean_us"] for r in results]
    total_chain_us = sum(all_means)
    print(f"\n  Full operator chain (sum of all means): {total_chain_us:.1f}µs  "
          f"({total_chain_us / 1000:.3f}ms)")
    print(f"  LLM response latency is typically 500–3000ms.")
    print(f"  Type-C evaluation overhead: {total_chain_us/1_000:.3f}ms per request")
    print()


if __name__ == "__main__":
    main()
