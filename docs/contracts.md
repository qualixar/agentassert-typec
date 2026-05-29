# Contract DSL Reference

AgentAssert Type-C contracts are YAML files that define behavioral invariants for AI agents. Version `dsl_version: "0.4"` adds 7 **process operators** for agentic flow control.

---

## Contract Structure

```yaml
dsl_version: "0.4"          # DSL version (0.3 = ABC compat, 0.4 = process operators)
contractspec: "1.0"         # ContractSpec format version
kind: agent                 # "agent" or "pipeline"
name: my-contract           # Unique contract name
description: "..."          # Human-readable purpose
version: "0.1"              # Your semantic version

invariants:
  hard: []                  # ABC v0.3 hard constraints (inherited)
  soft: []                  # ABC v0.3 soft constraints (inherited)
  process:                  # ← NEW in v0.4: process operators
    - ...

recovery:                   # Violation response strategy
  on_hard_violation: raise  # "raise" or "log_and_continue"
  on_soft_violation: log_and_continue

satisfaction:               # (p, δ, k) parameters
  p: 0.95
  delta: 0.10
  k: 3

drift:                      # Drift detection config
  window: 50
  thresholds:
    warning: 0.30
    critical: 0.60

reliability:                # Θ scorer config
  weights:
    compliance: 0.35
    drift: 0.25
    stress: 0.20
    recovery: 0.20
  deployment_threshold: 0.90
```

All fields except `contractspec`, `kind`, `name`, `description`, and `version` are optional.

---

## The 7 Process Operators (v0.4)

### 1. `tool_blocklist` — Hard

Blocks tool calls matching dangerous patterns. Evaluated before every action.

```yaml
- tool_blocklist:
    tools:
      - "rm -rf /*"           # Exact match
      - "curl|bash"           # Pipe pattern (curl piped to bash)
      - "wget|bash"           # Pipe pattern (wget piped to bash)
      - "*--no-verify"        # Wildcard: any glob matching --no-verify
    scope: session            # "session" or "turn"
```

| Field | Type | Description |
|---|---|---|
| `tools` | `list[str]` | Glob patterns for blocked tools. Supports `*` and `\|` pipe syntax. |
| `scope` | `"session"` or `"turn"` | How long the block applies. Default: `session`. |

**Decision:** `DENY` — request blocked with `ContractBreachError`.

---

### 2. `tool_allowlist` — Hard

Only allows tools in the specified list. All others denied.

```yaml
- tool_allowlist:
    tools: ["Read", "Write", "Edit", "Grep", "Glob"]
    scope: "skill:seo-content-optimizer"   # Any scope string
```

| Field | Type | Description |
|---|---|---|
| `tools` | `list[str]` | Exact tool names to allow. |
| `scope` | `str` | Named scope for this allowlist. |

**Decision:** `DENY` if tool NOT in the list.

---

### 3. `must_state` — Hard

Requires a named field to be stated before invoking tools matching a pattern. Designed for cost-control: "state the cost before calling any paid API."

```yaml
- must_state:
    field: "cost"
    before_tool_pattern: "tap_*|mcp__hermes*|paid_api_*"
    rationale: "Per cost-control policy"
```

| Field | Type | Description |
|---|---|---|
| `field` | `str` | Name of the state field that must exist. |
| `before_tool_pattern` | `str` | Regex for tools that require this field. |
| `rationale` | `str` | Human-readable reason (for violation logs). |

**Decision:** `DENY` if field not present in state before matching tool call.

---

### 4. `must_precede` — Soft

Marker ordering constraint. Requires marker `before` to appear before marker `after`. Designed for "challenge first, then recommend" patterns.

```yaml
- must_precede:
    before: "challenge"
    after: "recommendation"
    scope: turn              # "turn" or "session"
```

| Field | Type | Description |
|---|---|---|
| `before` | `str` | Marker that must appear first. |
| `after` | `str` | Marker that must not appear before `before`. |
| `scope` | `"turn"` or `"session"` | Scope of ordering. Default: `turn`. |

**Decision:** `soft_violation` → Θ penalty on violation. Does not block.

---

### 5. `context_budget` — Configurable

Token budget enforcement. Actions: warn, deny, or compress.

```yaml
- context_budget:
    max_tokens_per_turn: 60000
    action_on_breach: warn   # "warn", "deny", or "compress"
```

| Field | Type | Description |
|---|---|---|
| `max_tokens_per_turn` | `int` | Maximum tokens allowed per turn. Default: 60000. |
| `action_on_breach` | `"warn"`, `"deny"`, `"compress"` | Response to breach. Default: `warn`. |

| Action | Behavior |
|---|---|
| `warn` | Logs warning, allows request. |
| `deny` | Blocks request with error. |
| `compress` | Future: auto-compresses context (v0.5+). Currently logs and allows. |

---

### 6. `process_drift` — Soft

Real-time behavioral drift detection using Jensen-Shannon divergence on tool-call distributions.

```yaml
- process_drift:
    window_size: 10
    jsd_threshold: 0.30
    action: log              # "log", "warn", or "theta_penalty"
```

| Field | Type | Description |
|---|---|---|
| `window_size` | `int` | Sliding window for distribution snapshot. Default: 10. |
| `jsd_threshold` | `float` (0–1) | JSD value triggering the action. Default: 0.30. |
| `action` | `"log"`, `"warn"`, `"theta_penalty"` | Response to drift detection. |

| Action | Behavior |
|---|---|
| `log` | Records drift data silently. |
| `warn` | Records and emits warning. |
| `theta_penalty` | Applies penalty to Θ reliability score. |

Drift is computed incrementally using Welford's method — O(1) per update, no batch recomputation.

---

### 7. `judge_predicate` — Soft + Sampled (Async)

LLM-as-judge for qualitative rules that can't be expressed as deterministic operators. Runs asynchronously on a sample of turns.

```yaml
- judge_predicate:
    rubric: "Response shows L99 conviction (no 'depends', no 'either works')"
    sample_rate: 0.20
    model: ds-flash-free     # or "haiku"
    action_on_fail: theta_penalty
    cost_ceiling_usd_per_session: 0.0
```

| Field | Type | Description |
|---|---|---|
| `rubric` | `str` | Natural language description of what to check. |
| `sample_rate` | `float` (0–1) | Fraction of turns to evaluate. Default: 0.20. |
| `model` | `str` | Judge model: `ds-flash-free` ($0), `haiku` (paid). |
| `action_on_fail` | `"log"`, `"warn"`, `"theta_penalty"`, `"deny"` | Response to judge failure. Default: `theta_penalty`. |
| `cost_ceiling_usd_per_session` | `float` | Max spend on judge calls. Default: 0.10. Set 0.0 for free models. |

Judge routing: `ds-flash-free` (default, $0) → `haiku` (paid) → skip (fail-safe). Judges never block on failure — fail-open preserves user flow.

---

## Recovery Configuration

```yaml
recovery:
  on_hard_violation: raise            # "raise" → block + error
  on_soft_violation: log_and_continue  # "log_and_continue" → record + proceed
  strategies: []
```

| Field | Values | Description |
|---|---|---|
| `on_hard_violation` | `raise`, `log_and_continue` | What to do on hard constraint violations. |
| `on_soft_violation` | `log_and_continue`, `raise` | What to do on soft constraint violations. |

---

## (p, δ, k)-Satisfaction Parameters

```yaml
satisfaction:
  p: 0.95      # Probability hard constraints hold
  delta: 0.10   # Bound on soft deviations
  k: 3          # Recovery window (turns)
```

| Parameter | Range | Default | Meaning |
|---|---|---|---|
| `p` | (0, 1] | 0.95 | Target probability that hard constraints are satisfied. |
| `delta` | (0, 1] | 0.10 | Acceptable bound on soft constraint deviations. |
| `k` | [1, ∞) | 3 | Recovery window — max turns to self-correct. |

---

## Drift Configuration

```yaml
drift:
  window: 50
  weights:
    compliance: 0.6
    distributional: 0.4
  thresholds:
    warning: 0.30
    critical: 0.60
```

---

## Reliability (Θ) Configuration

```yaml
reliability:
  weights:
    compliance: 0.35     # C̄ — hard constraint satisfaction rate
    drift: 0.25          # 1-D̄ — complement of drift
    stress: 0.20         # 1/(1+E) — inverse event frequency
    recovery: 0.20       # S — recovery success rate
  deployment_threshold: 0.90
```

Θ formula: **Θ = 0.35 × C̄ + 0.25 × (1 - D̄) + 0.20 / (1 + E) + 0.20 × S**

---

## DSL Compatibility

| `dsl_version` | Operators Available | Notes |
|---|---|---|
| `"0.3"` | ABC hard/soft constraints only | Full backward compat |
| `"0.4"` | All ABC operators + 7 process operators | Current version |

Contracts with `dsl_version: "0.3"` load without error in v0.4. Process section is ignored.

---

## Template Contracts

Three templates ship with `agentassert-typec-claude-code`:

- **`safety-minimal`** — Blocklist only. Zero false positives. 20-line contract.
- **`partner-mode`** — All 6 operators (minus allowlist). Challenge-first, cost-before-paid, drift-detectable.
- **`full-governance`** — All 7 operators + ABC constraints + drift/reliability config.

See [Claude Code Guide](claude-code.md) for installation.

---

## Schema Validation

The contract YAML is validated at load time. Invalid contracts cause the proxy/SDK/hook to refuse startup.

Common validation errors:

| Error | Fix |
|---|---|
| `dsl_version must be "0.3" or "0.4"` | Check the version string is exactly `"0.3"` or `"0.4"`. |
| `tool_blocklist.tools must be list[str]` | Use `tools: ["cmd1", "cmd2"]` not `tools: cmd1`. |
| `must_precede.scope must be "turn" or "session"` | Use one of those two values. |
| `sample_rate must be > 0.0 and ≤ 1.0` | Use values like 0.20 for 20% sampling. |
