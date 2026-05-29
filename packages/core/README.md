# agentassert-typec-core

**Formal behavioral contract kernel. Provider-blind, transport-blind.**

This is the core engine — zero LLM deps, zero HTTP deps. Every adapter (proxy, SDK, hook) imports this.

## Features

- **7 Process Contract Operators** — tool_blocklist, tool_allowlist, must_state, must_precede, context_budget, process_drift, judge_predicate
- **ContractSpec DSL** — YAML-based, `dsl_version: "0.4"` for full Type-C, `dsl_version: "0.3"` for ABC compatibility
- **JSD Drift Tracker** — Welford-style incremental (O(1) per update), frozen baseline at window boundary
- **Θ Reliability Scorer** — Θ = 0.35C̄ + 0.25(1-D̄) + 0.20/(1+E) + 0.20S
- **Thread-safe SessionMonitor** — RLock-protected, evaluate() never blocks for >10ms
- **Pre-compiled AST** — all regex patterns compiled once at SessionStart

## Install

```bash
pip install agentassert-typec-core
```

## Quickstart

```python
from agentassert_typec_core import SessionMonitor, PreAction, DecisionResult

monitor = SessionMonitor.from_yaml("contract.yaml")
event = PreAction(session_id="s1", contract_id="c1", tool="Read", args={})
result = monitor.evaluate(event)
print(result.decision.name)  # ALLOW or DENY
```

## Optional: OTel

```bash
pip install agentassert-typec-core[otel]
```

## License

MIT
