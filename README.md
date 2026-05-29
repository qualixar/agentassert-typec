# AgentAssert Type-C — Formal Behavioral Contracts for AI Agents

> **"Set one env var. Get formal behavioral contracts on any agent, any model, any framework."**

[![CI](https://github.com/qualixar/agentassert-typec/actions/workflows/ci.yml/badge.svg)](https://github.com/qualixar/agentassert-typec/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![arXiv](https://img.shields.io/badge/arXiv-2602.22302-b31b1b.svg)](https://arxiv.org/abs/2602.22302)

AgentAssert Type-C is the **executive-function kernel** for AI agents. Drop it below your harness. Bound any model. Replace ad-hoc prompt engineering with formal contracts.

---

## 5-Minute Quickstart (Proxy — Zero Code Change)

```bash
# 1. Install
pip install agentassert-typec-proxy

# 2. Write a contract (or use a template)
cat > contract.yaml << 'EOF'
dsl_version: "0.4"
contractspec: "1.0"
kind: agent
name: safety-minimal
description: "Block destructive tool calls only."
version: "0.1"
invariants:
  process:
    - tool_blocklist:
        tools: ["rm -rf /*", "curl|bash"]
        scope: session
recovery:
  on_hard_violation: raise
  on_soft_violation: log_and_continue
EOF

# 3. Start the proxy
agentassert-proxy proxy start --contract contract.yaml

# 4. Point your agent at it
export ANTHROPIC_BASE_URL=http://localhost:9000/anthropic
export OPENAI_BASE_URL=http://localhost:9000/openai

# Done. Every API call is now contract-enforced.
```

---

## What AgentAssert Type-C Does

| Feature | Description |
|---|---|
| **7 Process Operators** | tool_blocklist, tool_allowlist, must_state, must_precede, context_budget, process_drift, judge_predicate |
| **Mathematical Bounds** | JSD drift detection (Welford incremental), Θ reliability scorer, (p, δ, k)-satisfaction |
| **Zero Code Change** | HTTP forwarding proxy — set `*_BASE_URL` env vars, done |
| **4 Provider Formats** | Anthropic, OpenAI, Gemini, OpenRouter |
| **Hot Reload** | Update contract YAML, proxy picks it up in 500ms |
| **Thread-Safe** | RLock-protected evaluator, concurrent request handling |
| **ABC v0.3 Compat** | Loads `dsl_version: "0.3"` contracts without error |

---

## Contract Operators

| Operator | Type | When | Description |
|---|---|---|---|
| `tool_blocklist` | Hard | PreAction | DENY if tool matches blocked pattern |
| `tool_allowlist` | Hard | PreAction | DENY if tool NOT in allowed list |
| `must_state` | Hard | PreAction | DENY if field not stated before tool |
| `must_precede` | Soft | TurnEnd | Θ penalty if marker order violated |
| `context_budget` | Configurable | ContextWindow | Warn/deny/compress on token limit breach |
| `process_drift` | Soft | TurnEnd | JSD on action distributions, configurable action |
| `judge_predicate` | Soft + sampled | Async | LLM-as-judge rubric evaluation |

---

## Installation Paths

```bash
# Python SDK — one-liner wrap
pip install agentassert-typec-sdk

# HTTP Proxy — zero-code middleware
pip install agentassert-typec-proxy

# Claude Code Hook — hooks into Claude Code CLI
pip install agentassert-typec-claude-code

# npm — Node.js ecosystem
npx agentassert-typec proxy start --contract contract.yaml

# Homebrew — macOS one-liner
brew install agentassert-typec
```

---

## Wedge Lines vs Competitors

- **vs Portkey:** "Portkey caps your spend. We cap your drift."
- **vs Inspect AI:** "Inspect tests your agent. AgentAssert governs it."
- **vs LiteLLM:** "LiteLLM picks your provider. We guarantee your behavior."
- **vs Guardrails:** "They filter words. We bound distributions."
- **vs LangGraph:** "LangGraph says what happens next. We say what must always be true."
- **Launch headline:** "Set one env var. Get formal behavioral contracts on any agent, any model, any framework."

---

## Architecture

```
                  ┌─────────────────────────────────────┐
                  │        agentassert-typec-core        │
                  │  ContractSpec engine · Predicate AST │
                  │  JSD drift · Θ scorer · Violation log│
                  │  NO HTTP deps · NO LLM deps          │
                  └──────────────┬──────────────────────┘
                                 │
        ┌────────────┬───────────┼───────────┬──────────┐
        ▼            ▼           ▼           ▼          ▼
     Proxy        SDK      Claude Code   (LiteLLM    TypeScript
    (flagship)             Hook           v0.5)      v0.7+)
```

---

## Research

- **Paper:** [arXiv:2602.22302](https://arxiv.org/abs/2602.22302) — "Formal Behavioral Contracts for AI Agents"
- **Drift metric:** Jensen-Shannon divergence on action distributions (Welford-style incremental, O(1) per update)
- **Reliability score:** Θ = 0.35C̄ + 0.25(1-D̄) + 0.20/(1+E) + 0.20S
- **Satisfaction:** (p, δ, k) framework — hard constraints satisfied with probability p, soft deviations bounded by δ, recovery within k turns

---

## License

MIT License — see [LICENSE](LICENSE). Commercial licenses available — see [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md).

---

## Links

- Website: [agentassert.com/typec](https://agentassert.com/typec)
- Paper: [arXiv:2602.22302](https://arxiv.org/abs/2602.22302)
- Repository: [github.com/qualixar/agentassert-typec](https://github.com/qualixar/agentassert-typec)
- Author: [@varunPbhardwaj](https://twitter.com/varunPbhardwaj)
