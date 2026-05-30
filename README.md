# AgentAssert Type-C

> **Formal behavioral contracts for AI agents. Set one env var. Get mathematical bounds on any agent, any model, any framework.**

<p align="center">
  <strong>Built by <a href="https://qualixar.com">Qualixar</a> · AI Reliability Engineering</strong><br/>
  <em>by <a href="https://twitter.com/varunPbhardwaj">Varun Pratap Bhardwaj</a></em>
</p>

---

[![CI](https://github.com/qualixar/agentassert-typec/actions/workflows/ci.yml/badge.svg)](https://github.com/qualixar/agentassert-typec/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/agentassert-typec-proxy.svg)](https://pypi.org/project/agentassert-typec-proxy/)
[![npm](https://img.shields.io/npm/v/agentassert-typec.svg)](https://www.npmjs.com/package/agentassert-typec)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![arXiv](https://img.shields.io/badge/arXiv-2602.22302-b31b1b.svg)](https://arxiv.org/abs/2602.22302)
[![Coverage](https://img.shields.io/badge/coverage-94%25-brightgreen.svg)](packages/core)
[![Tests](https://img.shields.io/badge/tests-292%20passed-brightgreen.svg)](packages/)
[![Twitter](https://img.shields.io/badge/Twitter-@varunPbhardwaj-1DA1F2.svg)](https://twitter.com/varunPbhardwaj)

---

## What Is This?

Your AI agent is only as reliable as the rules you enforce on it. Prompt instructions get ignored, drift goes undetected, and destructive tool calls slip through — because there was never a formal enforcement layer.

**AgentAssert Type-C is the executive-function kernel for AI agents.** It sits between your agent harness and any LLM API, enforcing behavioral contracts with mathematical guarantees backed by [published research](https://arxiv.org/abs/2602.22302).

```
Your agent code
       ↓
AgentAssert Type-C  ← formal contracts enforced here
       ↓
Anthropic / OpenAI / Gemini / OpenRouter
```

It is **not** a content filter (Guardrails AI does that). It is **not** an offline eval harness (Inspect AI does that). It is **not** a prompt wrapper. It is the **formal contract layer** — mathematical bounds on multi-turn behavior, enforced at the API call.

**Works with:** Claude Code · Antigravity · Cursor · Windsurf · Cline · any Python SDK · any CLI that supports `*_BASE_URL` env vars.

---

## 30-Second Install

```bash
# Flagship: zero code change — proxy mode
pip install agentassert-typec-proxy

# Start the proxy with a safety contract
agentassert-proxy start --contract safety-minimal.yaml

# Point your agent at it (works with any tool that reads env vars)
export ANTHROPIC_BASE_URL=http://localhost:9000/anthropic
export OPENAI_BASE_URL=http://localhost:9000/openai
```

That's it. Every API call your agent makes now passes through formal contract enforcement.

---

## Integration Guides

### Claude Code

Claude Code reads `ANTHROPIC_BASE_URL` natively, or can use the native hook adapter.

**Option A: HTTP Proxy (Zero Code Change)**
```bash
# In your terminal profile or active session:
export ANTHROPIC_BASE_URL=http://localhost:9000/anthropic

# Start Claude Code normally
claude
```

**Option B: Hook Adapter (Deep Hook Integration)**
```bash
pip install agentassert-typec-claude-code
agentassert-claude-code install --contract safety-minimal.yaml
```
The hook adapter integrates with Claude Code's native hook system (`PreToolUse`, `PostToolUse`, etc.) without requiring a proxy process.

---

### Antigravity (Antigravity IDE)

Antigravity IDE routes DeepSeek (OpenAI-compatible) and Gemini API calls. Set environment variables to intercept both:

```bash
# Intercept DeepSeek calls (OpenAI shape)
export OPENAI_BASE_URL=http://localhost:9000/openai

# Intercept Gemini calls
export GEMINI_BASE_URL=http://localhost:9000/gemini
```

Start the proxy using a contract containing the required limits (e.g., safety, cost ceiling):
```bash
agentassert-proxy start --contract safety-minimal.yaml --port 9000
```
Restart your Antigravity environment to apply.

---

### CommandCode

CommandCode (`cmd-mimo`, `cmd-ds`) uses global MCP and standard provider client configurations. To intercept all calls, point CommandCode's environment variables to the proxy:

```bash
export ANTHROPIC_BASE_URL=http://localhost:9000/anthropic
export OPENAI_BASE_URL=http://localhost:9000/openai
export GEMINI_BASE_URL=http://localhost:9000/gemini
export OPENROUTER_BASE_URL=http://localhost:9000/openrouter
```
Add these to your shell profile (e.g., `~/.zshrc`) so CommandCode sessions automatically load the proxy endpoints.

---

### Hermes CLI

Hermes (`hermes -z` or interactive) configuration lives in `~/.hermes/config.yaml`. Update the upstream URLs to route through the proxy:

```yaml
# Add / modify in ~/.hermes/config.yaml:
providers:
  openai:
    base_url: "http://127.0.0.1:9000/openai/v1"
  anthropic:
    base_url: "http://127.0.0.1:9000/anthropic/v1"
  gemini:
    base_url: "http://127.0.0.1:9000/gemini/v1"
  openrouter:
    base_url: "http://127.0.0.1:9000/openrouter/v1"
```

Alternatively, export the environment variables (e.g., `ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL`) before launching Hermes.

---

### Cursor

To run Cursor with contract governance:

**Option A: Global Environment (Command Line Launch)**
Export base URLs in your terminal and launch Cursor from the same session:
```bash
export ANTHROPIC_BASE_URL=http://localhost:9000/anthropic
export OPENAI_BASE_URL=http://localhost:9000/openai
cursor .
```

**Option B: Cursor settings UI**
1. Navigate to **Cursor Settings** -> **Models** -> **Custom API Keys / Base URLs**.
2. Enter the proxy endpoints:
   - OpenAI Compatible: `http://localhost:9000/openai/v1`
   - Anthropic: `http://localhost:9000/anthropic/v1`

---

### Windsurf

Windsurf's Cascade agent respects standard API base URLs:

**Option A: Environment Variables**
```bash
export ANTHROPIC_BASE_URL=http://localhost:9000/anthropic
export OPENAI_BASE_URL=http://localhost:9000/openai
windsurf .
```

**Option B: Settings UI**
In Windsurf Settings -> **AI Configurations** -> **Custom Endpoints**:
- OpenAI Base URL: `http://localhost:9000/openai/v1`
- Anthropic Base URL: `http://localhost:9000/anthropic/v1`

---

### OpenClaw

Configure OpenClaw's proxy endpoints in your `openclaw_config.json`:

```json
{
  "anthropic_base_url": "http://localhost:9000/anthropic/v1",
  "openai_base_url": "http://localhost:9000/openai/v1"
}
```
Or run the OpenClaw service with environment variables set (`export ANTHROPIC_BASE_URL=...`).

---

### Cline (VS Code Extension)

Route Cline calls through the proxy:
1. Open the Cline panel in VS Code and click the Settings icon.
2. Under **API Provider**, select **OpenAI Compatible** or **Anthropic**.
3. Set **Base URL** to:
   - OpenAI compatible: `http://localhost:9000/openai/v1`
   - Anthropic: `http://localhost:9000/anthropic/v1`
4. Set any dummy API key (e.g., `sk-assert-key`) as the proxy handles key routing.

---

### Python SDK (One-Line Wrap)

For Python developers using the Anthropic or OpenAI SDKs directly:

```bash
pip install agentassert-typec-sdk
```

```python
from anthropic import Anthropic
from agentassert_typec_sdk import wrap

# One line — every call is now contract-enforced
client = wrap(Anthropic(), "contract.yaml")

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "List the files in /"}]
)
```

Works with `anthropic.Anthropic`, `anthropic.AsyncAnthropic`, `openai.OpenAI`, `openai.AsyncOpenAI`.

---

### Node.js / npm

```bash
# Zero-install via npx
npx agentassert-typec proxy start --contract contract.yaml --port 9000

# Or install globally
npm install -g agentassert-typec
agentassert-typec proxy start --contract contract.yaml
```

---

### Homebrew (macOS)

```bash
brew install agentassert-typec
agentassert-proxy start --contract safety-minimal.yaml
```


---

## Your First Contract

A contract is a YAML file. Here's the minimal safety contract that blocks destructive tools:

```yaml
dsl_version: "0.4"
contractspec: "1.0"
kind: agent
name: safety-minimal
description: "Block destructive tool calls."
version: "0.1"

invariants:
  process:
    - tool_blocklist:
        tools: ["rm -rf /*", "curl|bash", "*--no-verify"]
        scope: session

recovery:
  on_hard_violation: raise
  on_soft_violation: log_and_continue
```

Here's a production contract with all 7 operators:

```yaml
dsl_version: "0.4"
contractspec: "1.0"
kind: agent
name: partner-mode
description: "Enforces partner-mode behavior: conviction, cost awareness, no drift."
version: "0.1"

invariants:
  process:
    # Require challenge before recommendation
    - must_precede:
        before: "challenge"
        after: "recommendation"
        scope: turn

    # State cost before paid API calls
    - must_state:
        field: "cost"
        before_tool_pattern: "tap_*|paid_api_*"

    # Block destructive tools
    - tool_blocklist:
        tools: ["rm -rf /*", "curl|bash"]
        scope: session

    # Cap token usage per turn
    - context_budget:
        max_tokens_per_turn: 60000
        action_on_breach: warn

    # Detect behavioral drift
    - process_drift:
        window_size: 10
        jsd_threshold: 0.30
        action: log

    # LLM-as-judge for qualitative rules (sampled, low cost)
    - judge_predicate:
        rubric: "Response shows clear conviction — no hedging, no 'depends'"
        sample_rate: 0.20
        model: ds-flash-free
        action_on_fail: theta_penalty
        cost_ceiling_usd_per_session: 0.10

recovery:
  on_hard_violation: raise
  on_soft_violation: log_and_continue

satisfaction:
  p: 0.95
  delta: 0.10
  k: 3
```

---

## The 10 Contract Operators

| Operator | Type | Trigger | What It Does |
|---|---|---|---|
| `tool_blocklist` | Hard | PreAction | DENY if tool matches blocked pattern |
| `tool_allowlist` | Hard | PreAction | DENY if tool not in allowed list |
| `must_state` | Hard | PreAction | DENY if required field not stated before tool call |
| `must_precede` | Soft | TurnEnd | Θ penalty if process step order is violated |
| `context_budget` | Configurable | ContextWindow | Warn / deny / compress on token limit breach |
| `process_drift` | Soft | TurnEnd | JSD on action distributions, configurable action |
| `judge_predicate` | Soft + sampled | Async | LLM-as-judge rubric evaluation, cost-capped |
| `pii_filter` | Hard / Soft | TurnEnd / PostAction | Redacts or blocks standard/custom PII patterns |
| `cost_ceiling` | Hard / Soft | PreAction / PostAction | Limits maximum session budget in USD (with token cost auto-calc) |
| `repetition_guard` | Hard / Soft | TurnEnd / PostAction | Detects and blocks/warns on repetitive loops or actions |

**Hard violations:** block the API call immediately, return a `ContractBreachError`.  
**Soft violations:** apply a Θ reliability penalty, log the incident, let the call through.

---

## What AgentAssert Type-C Is Not

| Competitor | What They Do | Why We're Different |
|---|---|---|
| **Portkey** | Budget caps, rate limits, observability | *"Portkey caps your spend. We cap your drift."* |
| **Guardrails AI** | String/regex output filters, content blocks | *"They filter words. We bound distributions."* |
| **Inspect AI** | Pre-deployment eval harness, offline testing | *"Inspect tests your agent. AgentAssert governs it."* |
| **LiteLLM** | Cross-provider routing, fallbacks | *"LiteLLM picks your provider. We guarantee your behavior."* |
| **LangGraph** | Multi-agent orchestration DAG | *"LangGraph says what happens next. We say what must always be true."* |

---

## Architecture

```
                 ┌────────────────────────────────────────┐
                 │         agentassert-typec-core          │
                 │  ContractSpec engine · Predicate AST    │
                 │  JSD drift · Θ scorer · Violation log   │
                 │  Pure Python — no HTTP, no LLM deps     │
                 └───────────────┬────────────────────────┘
                                 │
        ┌──────────┬─────────────┼──────────────┬─────────────┐
        ▼          ▼             ▼              ▼             ▼
  Proxy         SDK         Claude Code    (LiteLLM      (TypeScript
  (flagship)  (1-line wrap)  (native hooks)   v0.5)         v0.7+)
  any tool     any Python    Claude Code
  any language  SDK user      power users
```

**The proxy is the flagship.** If your tool supports `*_BASE_URL` env vars, you have zero integration work. That covers Claude Code, Antigravity, Cursor, Windsurf, Cline, OpenRouter CLI, Hermes, Gemini CLI, and any Python agent.

---

## Performance

Type-C is designed to be invisible at runtime. Benchmarks run on Apple M5 Pro, Python 3.14, 1,000 iterations each.

### Operator Evaluation Speed (all 10 operators, no API key needed)

| Operator | Mean | p99 |
|---|---|---|
| `tool_blocklist` (deny path) | 0.8µs | 1.0µs |
| `tool_blocklist` (allow path) | 0.3µs | 0.4µs |
| `tool_allowlist` | 0.3µs | 0.3µs |
| `must_precede` (deny path) | 0.8µs | 0.9µs |
| `cost_ceiling` | 0.9µs | 1.0µs |
| `repetition_guard` | 0.3µs | 0.3µs |
| `pii_filter` (6 pattern types) | 0.2µs | 0.3µs |
| `drift_tracker` update | 0.2µs | 0.3µs |
| **All 10 operators combined** | **4.4µs** | **< 6µs** |

**0.004ms total** for the full operator chain. Typical LLM response latency is 500–3,000ms — Type-C evaluation is < 0.1% of that.

### Proxy Round-Trip Overhead (200 requests, mock upstream, no LLM cost)

| Metric | Direct | Via Type-C | Added |
|---|---|---|---|
| Mean latency | 0.45ms | 1.30ms | **+0.85ms** |
| p99 latency | 0.60ms | 1.90ms | **+1.30ms** |

**+0.85ms mean overhead per request.** Invisible in practice — network RTT to any LLM provider alone exceeds this by 50–100×.

Reproduce with: `uv run python scripts/bench_operators.py` and `uv run python scripts/bench_proxy_overhead.py`

---

## The Math Behind the Contracts

AgentAssert Type-C is backed by [arXiv:2602.22302](https://arxiv.org/abs/2602.22302) — *"Formal Behavioral Contracts for AI Agents"*.

**Θ Reliability Score** — a continuous measure of how faithfully an agent follows its contract over time:
```
Θ = 0.35·C̄ + 0.25·(1 − D̄) + 0.20/(1 + E) + 0.20·S
```
Where C̄ = constraint satisfaction rate, D̄ = mean JSD drift, E = error rate, S = stability score.

**JSD Drift Detection** — Jensen-Shannon divergence on action distributions, computed in O(1) per update using Welford's incremental algorithm. Tracks behavioral drift without storing full history.

**(p, δ, k)-Satisfaction** — hard constraints satisfied with probability p, soft deviations bounded by δ, recovery within k turns. Gives you a formal proof of behavioral bounds.

---

## Use Cases

### Use Case 1: Protect Production Agent from Destructive Actions

You run a coding agent in production. One bad session could `rm -rf` a directory. The proxy blocks it before the API call is ever made.

```bash
agentassert-proxy start --contract safety-minimal.yaml
export ANTHROPIC_BASE_URL=http://localhost:9000/anthropic
```

### Use Case 2: Compress CLAUDE.md with Formal Contracts

Your CLAUDE.md has grown to 500+ lines of rules that get ignored under context pressure. Replace the enforcement parts with a contract — the proxy enforces them mathematically, not by hoping the model reads them.

```yaml
# Instead of 50 lines in CLAUDE.md about "never skip LLD phase"
# and "always state cost before paid API call":
invariants:
  process:
    - must_state:
        field: "cost"
        before_tool_pattern: "tap_*"
    - tool_blocklist:
        tools: ["rm -rf /*", "--no-verify"]
```

See the [Case Study](docs/case-study.md) — 48% CLAUDE.md compression with mathematically enforced equivalent bounds.

### Use Case 3: Drift Detection Across a Long Session

You want to know if your agent's behavior changes over a 4-hour coding session — are tool call patterns drifting? The `process_drift` operator fires silently when JSD exceeds threshold:

```yaml
- process_drift:
    window_size: 20
    jsd_threshold: 0.25
    action: log          # or: warn, theta_penalty, raise
```

### Use Case 4: LLM-as-Judge Guardrails (Sampled, Cost-Free)

You want to catch low-conviction responses ("it depends", "either works") without reading every output yourself. Sample 20% of responses to a free model judge:

```yaml
- judge_predicate:
    rubric: "Response gives a direct recommendation with clear reasoning. Fails if hedging."
    sample_rate: 0.20
    model: ds-flash-free   # OpenRouter free tier — $0
    action_on_fail: theta_penalty
    cost_ceiling_usd_per_session: 0.05
```

---

## Packages

| Package | Install | Use For |
|---|---|---|
| `agentassert-typec-proxy` | `pip install agentassert-typec-proxy` | Any CLI, any language, zero code change |
| `agentassert-typec-sdk` | `pip install agentassert-typec-sdk` | Python SDK users (Anthropic / OpenAI direct) |
| `agentassert-typec-claude-code` | `pip install agentassert-typec-claude-code` | Claude Code hook integration |
| `agentassert-typec-core` | pulled automatically | Pure kernel (no HTTP/LLM deps) |
| `agentassert-typec` (npm) | `npx agentassert-typec` | Node.js / zero-install proxy |

---

## Documentation

| Doc | Contents |
|---|---|
| [Getting Started](docs/getting-started.md) | All 5 integration paths with full examples |
| [Contract DSL Reference](docs/contracts.md) | All 10 operators, YAML schema, examples |
| [Proxy Guide](docs/proxy.md) | Multi-provider setup, streaming, hot reload |
| [SDK Guide](docs/sdk.md) | Python SDK wrap, async, OpenAI + Anthropic |
| [Claude Code Guide](docs/claude-code.md) | Hook adapter, templates, installer |
| [Architecture](docs/architecture.md) | Package design, 7-event protocol, kernel internals |
| [Mathematics](docs/math.md) | JSD drift, Θ scorer, (p,δ,k)-satisfaction |
| [Case Study](docs/case-study.md) | CLAUDE.md compression with measured results |
| [FAQ](docs/faq.md) | Licensing questions, AGPL FAQ, commercial use |

---

## License

MIT License — see [LICENSE](LICENSE).  
For commercial embedding, hosted SaaS, or enterprise deployments requiring warranty and SLA support, contact us: [COMMERCIAL-LICENSE.md](docs/licensing.md)

---

## About

**AgentAssert Type-C** is a product of [Qualixar](https://qualixar.com) — AI Reliability Engineering.

Built by **Varun Pratap Bhardwaj**  
→ Twitter: [@varunPbhardwaj](https://twitter.com/varunPbhardwaj)  
→ YouTube: [@myhonestdiary](https://youtube.com/@myhonestdiary)  
→ Email: varun.pratap.bhardwaj@gmail.com

**AgentAssert Type-C** is a sub-product of **AgentAssert ABC** ([arXiv:2602.22302](https://arxiv.org/abs/2602.22302)), which targets enterprise multi-agent governance. Type-C is the developer-first wedge — free, pip-installable, MIT-licensed.

---

## Links

- **GitHub:** [github.com/qualixar/agentassert-typec](https://github.com/qualixar/agentassert-typec)
- **PyPI (proxy):** [pypi.org/project/agentassert-typec-proxy](https://pypi.org/project/agentassert-typec-proxy/)
- **npm:** [npmjs.com/package/agentassert-typec](https://www.npmjs.com/package/agentassert-typec)
- **Research paper:** [arXiv:2602.22302](https://arxiv.org/abs/2602.22302)
- **Qualixar:** [qualixar.com](https://qualixar.com)
- **Twitter:** [@varunPbhardwaj](https://twitter.com/varunPbhardwaj)

---

*AgentAssert Type-C — AI Reliability Engineering by [Qualixar](https://qualixar.com)*
