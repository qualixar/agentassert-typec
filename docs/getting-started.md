# Getting Started

Choose your integration path. All paths share the same core kernel.

---

## Path 1: HTTP Proxy (Zero Code Change)

Best for: any CLI, any language, any framework.

```bash
pip install agentassert-typec-proxy
```

Write a contract:

```bash
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
```

Start the proxy:

```bash
agentassert-proxy proxy start --contract contract.yaml --port 9000
```

Point your agent at it:

```bash
export ANTHROPIC_BASE_URL=http://localhost:9000/anthropic
export OPENAI_BASE_URL=http://localhost:9000/openai
export GEMINI_BASE_URL=http://localhost:9000/gemini
export OPENROUTER_BASE_URL=http://localhost:9000/openrouter
```

All provider API calls now flow through the contract layer. No code changes needed.

[Full Proxy Guide →](proxy.md)

---

## Path 2: Python SDK (One-Line Wrap)

Best for: Python developers using Anthropic or OpenAI SDKs directly.

```bash
pip install agentassert-typec-sdk
```

```python
from anthropic import Anthropic
from agentassert_typec_sdk import wrap

client = wrap(Anthropic(), "contract.yaml")

# Every call is now contract-enforced
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}]
)
```

Supported clients: `anthropic.Anthropic`, `anthropic.AsyncAnthropic`, `openai.OpenAI`, `openai.AsyncOpenAI`.

[Full SDK Guide →](sdk.md)

---

## Path 3: Claude Code Hook (Zero Code Change)

Best for: Claude Code CLI power users.

```bash
pip install agentassert-typec-claude-code
```

Install the hook:

```bash
agentassert-claude-code install --contract safety-minimal.yaml
```

Check status:

```bash
agentassert-claude-code status
```

Remove the hook:

```bash
agentassert-claude-code uninstall
```

Three contract templates ship with the package: `safety-minimal`, `partner-mode`, `full-governance`.

[Full Claude Code Guide →](claude-code.md)

---

## Path 4: npm (Node.js Ecosystem)

```bash
npx agentassert-typec proxy start --contract contract.yaml --port 9000
```

Same as the HTTP proxy, zero-install via npm. Downloads the pre-built binary.

---

## Path 5: Homebrew (macOS)

```bash
brew install agentassert-typec
agentassert-proxy proxy start --contract contract.yaml
```

---

## Your First Contract

Here's a production-ready contract with all 7 operators:

```yaml
dsl_version: "0.4"
contractspec: "1.0"
kind: agent
name: full-governance
description: "Full behavioral contract with all process operators."
version: "0.1"

invariants:
  process:
    # 1. Require challenge before recommendation
    - must_precede:
        before: "challenge"
        after: "recommendation"
        scope: turn

    # 2. State cost before paid API calls
    - must_state:
        field: "cost"
        before_tool_pattern: "tap_*|paid_api_*"
        rationale: "Per cost-control policy"

    # 3. Block destructive tools
    - tool_blocklist:
        tools:
          - "rm -rf /*"
          - "curl|bash"
          - "*--no-verify"
        scope: session

    # 4. Restrict tools for specific skills
    - tool_allowlist:
        tools: ["Read", "Write", "Edit", "Grep", "Glob"]
        scope: "skill:seo-content-optimizer"

    # 5. Cap token usage per turn
    - context_budget:
        max_tokens_per_turn: 60000
        action_on_breach: warn

    # 6. Detect behavioral drift
    - process_drift:
        window_size: 10
        jsd_threshold: 0.30
        action: log

    # 7. LLM-as-judge for qualitative rules
    - judge_predicate:
        rubric: "Response shows L99 conviction (no 'depends', no 'either works')"
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

[Full DSL Reference →](contracts.md)

---

## Verifying It Works

After starting the proxy, test that blocked tools actually get blocked:

```bash
# This call should return a ContractBreachError
curl -X POST http://localhost:9000/anthropic/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-sonnet-4-6",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Run: rm -rf /"}]
  }'
```

The proxy returns a 400 with the violation details instead of forwarding to Anthropic.

---

## Next Steps

- [Contract DSL Reference](contracts.md) — all 7 operators in detail
- [Case Study](case-study.md) — compressing CLAUDE.md by 48%
- [Mathematics](math.md) — JSD drift, Θ scorer, (p,δ,k)
- [FAQ](faq.md)
