# AgentAssert Type-C

**The executive-function kernel for AI agents. Formal behavioral contracts backed by published research.**

Set one env var. Get formal behavioral contracts on any agent, any model, any framework.

---

## What Is Type-C?

AgentAssert Type-C is a **runtime contract layer** that sits between your agent code and any LLM API provider. It intercepts every API call and enforces formal behavioral contracts — mathematical guarantees that your agent's behavior stays within defined bounds.

| You Write | We Enforce |
|---|---|
| `tool_blocklist: ["rm -rf /*", "curl\|bash"]` | Destructive commands blocked at API level |
| `context_budget: max_tokens_per_turn: 60000` | Token bloat caught before it costs you |
| `process_drift: jsd_threshold: 0.30` | Behavioral drift detected in real-time |
| `judge_predicate: rubric: "No 'depends', no 'either works'"` | L99 conviction enforced by LLM-as-judge |

**Backed by** [arXiv:2602.22302](https://arxiv.org/abs/2602.22302) — "Formal Behavioral Contracts for AI Agents."

---

## Why Type-C?

LLMs have zero executive function. They're high-knowledge interns. The intelligence comes from the **wrapper** — tool protocols, hook systems, verification loops. Type-C gives you formal, vendor-neutral behavioral contracts that plug into any harness.

- **vs Portkey:** "Portkey caps your spend. We cap your drift."
- **vs Inspect AI:** "Inspect tests your agent. AgentAssert governs it."
- **vs LiteLLM:** "LiteLLM picks your provider. We guarantee your behavior."
- **vs Guardrails:** "They filter words. We bound distributions."
- **vs LangGraph:** "LangGraph says what happens next. We say what must always be true."

---

## 5-Minute Quickstart

```bash
# 1. Install the proxy
pip install agentassert-typec-proxy

# 2. Write a contract
cat > contract.yaml << 'EOF'
dsl_version: "0.4"
contractspec: "1.0"
kind: agent
name: safety-minimal
description: "Block destructive tool calls."
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

## Integration Paths

| Path | Install | Code Change | Use When |
|---|---|---|---|
| **HTTP Proxy** | `pip install agentassert-typec-proxy` | Zero | Any CLI, any language, any framework |
| **Python SDK** | `pip install agentassert-typec-sdk` | One line | Direct Anthropic/OpenAI SDK usage |
| **Claude Code Hook** | `pip install agentassert-typec-claude-code` | Zero | Claude Code CLI users |
| **npm** | `npx agentassert-typec proxy start` | Zero | Node.js ecosystem |

---

## The Math

| Concept | What It Does |
|---|---|
| **7 Process Operators** | tool_blocklist, tool_allowlist, must_state, must_precede, context_budget, process_drift, judge_predicate |
| **JSD Drift Detection** | Jensen-Shannon divergence on action distributions (Welford-style incremental, O(1) per update) |
| **Θ Reliability Score** | Θ = 0.35C̄ + 0.25(1-D̄) + 0.20/(1+E) + 0.20S |
| **(p, δ, k)-Satisfaction** | Hard constraints satisfied with probability p, soft deviations bounded by δ, recovery within k turns |
| **Lyapunov Stability** | Drift distribution proven stable under OU dynamics |

---

## Package Layout

```
agentassert-typec-core         ← Pure kernel (no HTTP/LLM deps)
agentassert-typec-proxy        ← Flagship HTTP proxy
agentassert-typec-sdk          ← Python SDK wrap()
agentassert-typec-claude-code  ← Claude Code hook adapter
```

---

## License

MIT License. See [LICENSE](LICENSE). Commercial support available — see [Licensing](licensing.md).

---

## Links

- [Getting Started](getting-started.md)
- [Contract DSL Reference](contracts.md)
- [Architecture](architecture.md)
- [Mathematics](math.md)
- [API Reference](api-reference.md)
- [FAQ](faq.md)
- [GitHub: qualixar/agentassert-typec](https://github.com/qualixar/agentassert-typec)
- [Paper: arXiv:2602.22302](https://arxiv.org/abs/2602.22302)
- [Author: @varunPbhardwaj](https://twitter.com/varunPbhardwaj)
