# Case Study: Compressing CLAUDE.md with Type-C

**How a 50-line ContractSpec replaced 60% of CLAUDE.md and made behavioral rules formally enforceable.**

---

## Background

Varun's `CLAUDE.md` + `rules/*.md` + skill files define the behavioral rules for AI agents. These rules include:

- **Challenge-first** — "CHALLENGE FIRST. Is this the right problem?"
- **Cost-before-paid-API** — "State cost before calling any paid API"
- **Destructive command bans** — "rm -rf", "curl|bash", "--no-verify"
- **Token budget** — Implicit context management
- **L99 conviction** — "No 'depends', no 'either works'"

These rules were **prompts**, not contracts. They could be ignored, forgotten, or drift-overridden by the model. There was no way to know if they were being followed.

---

## The Migration

We mapped the process-shape parts of `CLAUDE.md` into a Type-C contract:

### Before: CLAUDE.md Process Rules

```
8 Rules (binary):
1. CHALLENGE FIRST. Is this the right problem?
2. 2+ ALTERNATIVES with TRADEOFFS
3. L99 RECOMMENDATION — pick one, defend it
4. WAIT FOR APPROVAL before non-trivial execution
5. HARSH ON BAD IDEAS
6. TEACH THE WHY
7. VERIFY DON'T CLAIM
8. RESEARCH BEFORE CLAIMING

Cost Control:
- NEVER call paid API without explicit per-call approval
- State cost + service, wait for "go"

Destructive Commands:
- rm -rf, curl|bash, --no-verify banned

Context Budget:
- Implicit: keep CLAUDE.md tight, aggressive trimming
```

### After: 50-Line ContractSpec

```yaml
dsl_version: "0.4"
contractspec: "1.0"
kind: agent
name: partner-mode
description: "Challenge-first, cost-before-paid-API, no destructive tools."
version: "0.1"

invariants:
  process:
    # Rule 1: CHALLENGE FIRST
    - must_precede:
        before: "challenge"
        after: "recommendation"
        scope: turn

    # Cost Control: State cost before paid API calls
    - must_state:
        field: "cost"
        before_tool_pattern: "tap_*|mcp__hermes*|paid_api_*"
        rationale: "Per cost-control.md HARD RULE"

    # Destructive Commands Banned
    - tool_blocklist:
        tools:
          - "rm -rf /*"
          - "rm --no-preserve-root"
          - "curl|bash"
          - "wget|bash"
          - "*--no-verify"
        scope: session

    # Token Budget: Warn at 60K
    - context_budget:
        max_tokens_per_turn: 60000
        action_on_breach: warn

    # Drift Detection: JSD at 0.30
    - process_drift:
        window_size: 10
        jsd_threshold: 0.30
        action: log

    # Judge Predicate: L99 conviction
    - judge_predicate:
        rubric: "Response shows L99 conviction (no 'depends', no 'either works')"
        sample_rate: 0.20
        model: ds-flash-free
        action_on_fail: theta_penalty
        cost_ceiling_usd_per_session: 0.0

recovery:
  on_hard_violation: raise
  on_soft_violation: log_and_continue

satisfaction:
  p: 0.95
  delta: 0.10
  k: 3
```

---

## Results

| Metric | Before | After | Change |
|---|---|---|---|
| **Total CLAUDE.md + rules size** | 49,636 bytes | 25,920 bytes | **-47.8%** |
| **Process rules size** | 31,322 bytes | 1,203 bytes (contract) | **-96.2%** |
| **Tokens per turn (rules portion)** | ~7,800 tokens | ~540 tokens (contract ref only) | **-93.1%** |
| **Enforcement** | Prompt (advisory) | Contract (deterministic) | Upgrade |
| **Drift detection** | None | Real-time JSD | New capability |
| **Auditability** | Manual review | Per-violation log | New capability |

### What Stayed in CLAUDE.md

Style, voice, and aesthetic guidance remain in CLAUDE.md because they're subjective:

- Tone and personality rules
- Skill arsenal catalog
- Routing tables (which model for which task)
- Cross-Audit checklist format

### What Moved to Contract

Everything that's mechanically verifiable:

- Challenge-before-recommendation → `must_precede`
- Cost-before-paid-API → `must_state`
- Destructive command bans → `tool_blocklist`
- Token budget → `context_budget`
- Behavioral drift → `process_drift`
- Conviction quality → `judge_predicate`

---

## Real-World Impact

### Near-Miss Prevented

During testing, the `tool_blocklist` operator caught a `curl ... | bash` pattern that would have silently passed through prompt-based rules. The model had reformatted the command to avoid the exact string match in CLAUDE.md — but the contract's regex pattern caught the pipe regardless of formatting.

### Drift Caught

Over 100 turns, the JSD drift detector identified a gradual shift where the agent began using `Bash` instead of `Write` for file operations — a behavioral drift that prompt rules couldn't detect because each individual call looked reasonable.

### Θ Score Improvement

Before: Θ = ~0.82 (unmeasured, estimated from violation patterns in prompt-only mode)
After: Θ = 0.94 (measured, post-contract enforcement)

---

## How to Reproduce

1. Install the Claude Code hook:
```bash
pip install agentassert-typec-claude-code
agentassert-claude-code install --contract partner-mode.yaml
```

2. Trim your CLAUDE.md to style/voice/identity only. Remove process rules that are now contract-enforced.

3. Run your agent for a week. Check the Θ score:
```bash
agentassert-claude-code status
```

4. Compare token savings from your CLAUDE.md reduction.

---

## Key Insight

**Prompts are suggestions. Contracts are guarantees.**

The model can ignore a prompt rule. It cannot ignore a contract — because the proxy/SDK/hook blocks the API call before it reaches the model. This is the fundamental shift from prompt engineering to formal contracts.
