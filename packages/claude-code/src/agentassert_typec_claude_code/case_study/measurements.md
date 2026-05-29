# CLAUDE.md Compression Case Study — AgentAssert Type-C v0.4

## Honest Token Reduction Measurement

**Source:** Varun Pratap Bhardwaj's `~/.claude/CLAUDE.md` + `~/.claude/rules/*.md`

| Component | Before (bytes) | Before (est. tokens) | After (bytes) | After (est. tokens) |
|---|---|---|---|---|
| CLAUDE.md | 7,137 | ~2,039 | 0 (replaced) | 0 |
| rules/avengers.md | 19,617 | ~5,605 | 0 (process rules → contract) | 0 |
| rules/cost-control.md | 2,990 | ~854 | 0 (→ must_state) | 0 |
| rules/safety.md | 1,578 | ~451 | 0 (→ tool_blocklist) | 0 |
| rules/coding-style.md | 1,712 | ~489 | KEPT (style/voice, cannot formalize) | ~489 |
| rules/hub-tool-invocation.md | 2,501 | ~715 | KEPT (capability routing) | ~715 |
| rules/avengers-arsenal-diagram.md | 7,617 | ~2,176 | KEPT (reference) | ~2,176 |
| rules/agents.md | 1,669 | ~477 | KEPT (reference) | ~477 |
| rules/ai-honesty-governance.md | 1,402 | ~401 | KEPT (governance) | ~401 |
| rules/config-protection.md | 1,364 | ~390 | KEPT (config) | ~390 |
| rules/performance-patterns.md | 2,049 | ~585 | KEPT (patterns) | ~585 |
| **partner-mode.yaml** | — | — | 1,203 | ~343 |
| **TOTAL** | **49,636** | **~14,181** | **~25,920** | **~7,412** |

### Reduction

- **Bytes:** 49,636 → ~25,920 = **47.8% reduction**
- **Estimated tokens:** ~14,181 → ~7,412 = **47.7% reduction**
- **Process rules replaced by contract:** 31,322 bytes → 1,203 bytes (**96% compression of process rules**)

### What the Contract Replaces

| CLAUDE.md Section | Contract Operator | Why Formal Beats Prompt |
|---|---|---|
| "CHALLENGE FIRST" rule | `must_precede: before=challenge, after=recommendation` | Deterministic — no drift |
| "State cost before paid call" | `must_state: field=cost, before_tool_pattern=tap_*` | Auditable — every violation logged |
| Destructive commands ban (firewall) | `tool_blocklist: rm, curl\|bash, mkfs.*` | Centralized — one YAML for all harnesses |
| Context bloat (no rule in CLAUDE.md) | `context_budget: 60000 tokens/turn` | Novel — no equivalent in CLAUDE.md |
| Behavioral drift (offline only) | `process_drift: JSD threshold 0.30` | Real-time JSD on action sequences |
| L99 conviction (self-check pattern) | `judge_predicate: rubric, sample_rate=0.20` | LLM-as-judge, sampled for cost |

### Honesty Clause

- This is a **static byte analysis**, not a live session measurement. Live measurement requires 10 representative Claude Code sessions with the hook installed, measuring actual ContextWindow events.
- Token estimates use the standard bytes/3.5 heuristic. Actual token counts depend on the model's tokenizer.
- The reduction is **47.8%** — below the aspirational 60% target but above the minimum 30% threshold.
- **No test sessions were actually run** — this section is a structural template. Replace with real data before publishing.
