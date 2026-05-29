# Mathematics

AgentAssert Type-C provides mathematical guarantees for AI agent behavior. This page explains the three mathematical foundations.

---

## 1. Jensen-Shannon Divergence (JSD) Drift Detection

### What It Detects

JSD measures how much your agent's action distribution has drifted from its established baseline. If your agent normally uses `Read` 50% of the time, `Write` 20%, `Bash` 30%, and suddenly starts using `Bash` 80% — JSD catches it.

### How It's Computed

**Welford-style incremental update** — O(1) per new action. No batch recomputation.

For distributions P and Q over action categories:

```
JSD(P || Q) = 0.5 × KL(P || M) + 0.5 × KL(Q || M)
where M = 0.5 × (P + Q)
and KL(P || Q) = Σ P(i) × log(P(i) / Q(i))
```

- **JSD ∈ [0, 1]** where 0 = identical distributions, 1 = maximally different
- JSD is symmetric and bounded (unlike KL divergence)
- Square root of JSD is a metric

### Baseline

A baseline distribution is frozen after `window_size` observations. Thereafter, each new window is compared against this frozen baseline. This catches slow drift that a rolling comparison might miss.

### Configuration

```yaml
- process_drift:
    window_size: 10
    jsd_threshold: 0.30
    action: log
```

| Parameter | What It Means |
|---|---|
| `window_size = 10` | Take a distribution snapshot every 10 actions |
| `jsd_threshold = 0.30` | Trigger if JSD between current window and baseline exceeds 0.30 |
| `action: log` | Record the drift event (other options: `warn`, `theta_penalty`) |

### Why JSD Not KL

KL divergence is asymmetric and unbounded. JSD is:
- Symmetric: `JSD(P, Q) = JSD(Q, P)` — drift from A→B equals drift from B→A
- Bounded: always in [0, 1], normalized
- A true metric (its square root) — satisfies triangle inequality

---

## 2. Θ (Theta) Reliability Score

### Formula

```
Θ = 0.35 × C̄  +  0.25 × (1 - D̄)  +  0.20 / (1 + E)  +  0.20 × S
```

| Symbol | Term | Weight | Meaning |
|---|---|---|---|
| C̄ | Compliance rate | 0.35 | Fraction of hard constraints that pass |
| D̄ | Average drift | 0.25 | Average JSD over session (penalized: we use 1-D̄) |
| E | Event frequency | 0.20 | Number of violation events (penalized: we use 1/(1+E)) |
| S | Recovery success rate | 0.20 | Fraction of soft violations recovered within k turns |

### Range

Θ ∈ [0, 1]. Higher is better.

### Deployment Threshold

Default: **Θ ≥ 0.90** for deployment. Agents below this threshold should have their contracts reviewed or constraints tightened.

### Penalty Application

- `process_drift` with `action: theta_penalty` applies -0.03 to Θ per drift event
- `judge_predicate` with `action_on_fail: theta_penalty` applies -0.03 per failed judge sample
- `must_precede` violations apply -0.01 per violation

### Custom Weights

```yaml
reliability:
  weights:
    compliance: 0.40    # Higher weight on hard constraint satisfaction
    drift: 0.30
    stress: 0.15
    recovery: 0.15
  deployment_threshold: 0.85
```

Weights must sum to ≤ 1.0.

---

## 3. (p, δ, k)-Satisfaction Framework

Formal satisfaction guarantee for your behavioral contract.

### Definition

A contract is **(p, δ, k)-satisfied** if:

1. **Hard constraints** are met with probability at least **p** (per turn)
2. **Soft constraint deviations** are bounded by **δ**
3. **Recovery** from any violation occurs within **k** turns

### Parameters

```yaml
satisfaction:
  p: 0.95      # 95% probability hard constraints hold
  delta: 0.10   # Soft deviations ≤ 0.10
  k: 3          # Recover within 3 turns
```

### Interpretation

| (p, δ, k) | Meaning |
|---|---|
| (0.95, 0.10, 3) | 95% of tool calls comply. Deviations are small. Agent self-corrects within 3 turns. |
| (0.99, 0.05, 1) | Extremely strict. 99% compliance. Near-zero deviation. Immediate recovery. |
| (0.90, 0.20, 5) | Relaxed. Suitable for non-critical agents. |

### Monitoring

The `SessionMonitor` tracks actual (p, δ, k) values over a session and reports them at `SessionEnd` via the drift report.

---

## 4. Contract Decision Logic

### PreAction Evaluation (Hard Operators)

```
evaluate(request, contract):
  result = ALLOW

  # 1. Tool blocklist check (Hard → DENY)
  if any(tool matches blocklist.pattern):
    return DENY("tool_blocklist", matched_pattern)

  # 2. Tool allowlist check (Hard → DENY)
  if allowlist exists AND tool NOT in allowlist:
    return DENY("tool_allowlist", tool)

  # 3. must_state check (Hard → DENY)
  for each must_state rule:
    if tool matches before_tool_pattern AND field not in state:
      return DENY("must_state", field)

  # 4. context_budget check (Configurable)
  if token_count > max_tokens_per_turn:
    if action_on_breach == "deny": return DENY
    if action_on_breach == "warn": log_warning

  return ALLOW
```

### PostAction / TurnEnd Evaluation (Soft Operators)

```
evaluate_post(response, contract):
  # 5. Update drift distribution
  drift_tracker.observe(tool)

  # 6. Check must_precede (Soft → Θ penalty)
  if after seen before before:
    violation_log.record_soft("must_precede")

  # 7. JSD drift check (Soft)
  if jsd > threshold:
    action: log | warn | theta_penalty

  # 8. asyncio: schedule judge_predicate (Soft + Sampled)
  if random() < sample_rate:
    schedule_judge_evaluation(rubric, output)

  # Update (p, δ, k) statistics
  # Update Θ score
```

### Why Hard Deny vs Soft Penalty

| Operator | Type | Why |
|---|---|---|
| `tool_blocklist` | Hard `DENY` | Destructive — must block, can't just warn |
| `tool_allowlist` | Hard `DENY` | Unauthorized tools must be gated upstream |
| `must_state` | Hard `DENY` | Cost rules must gate before spend |
| `context_budget` | Configurable | Context bloat is a cost concern, not always safety |
| `must_precede` | Soft | Process violations hurt quality, not safety |
| `process_drift` | Soft | Drift means "behavior changed" not "behavior is dangerous" |
| `judge_predicate` | Soft | Qualitative — subjective assessment, not deterministic |
