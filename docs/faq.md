# Frequently Asked Questions

---

### What is AgentAssert Type-C?

A runtime contract layer that sits between your agent code and LLM APIs. It intercepts every call and enforces formal behavioral contracts — blocking dangerous tool calls, detecting drift, capping token usage, and running LLM-as-judge evaluations.

---

### How is this different from prompt engineering?

Prompts are advisory — the model can ignore them. Contracts are enforced at the API level — the proxy blocks the request before it reaches the model. You get deterministic enforcement, not probabilistic compliance.

---

### Does Type-C add latency?

The proxy adds **< 30ms p99 overhead** (excluding provider round-trip time). Predicate evaluation runs against a pre-compiled AST, drift is computed incrementally (O(1) per update), and judge predicates run asynchronously off the hot path.

---

### Which models does it work with?

Type-C is model-agnostic. It intercepts API calls — it doesn't care which model is behind the provider. Works with Anthropic (Claude), OpenAI (GPT), Gemini, and any model routed through OpenRouter.

---

### Do I need to change my agent code?

Zero code changes with the HTTP proxy. One line change with the Python SDK (`wrap(client)`). Zero changes with the Claude Code hook.

---

### Can I use Type-C with Cursor / Cline / Antigravity?

Yes — via the HTTP proxy. Set `ANTHROPIC_BASE_URL` or `OPENAI_BASE_URL` to point at the proxy and all your CLI tools are covered.

---

### What happens if the proxy crashes?

The proxy is designed to fail-open for internal errors (predicate eval throws, judge model down). Hard operators (`tool_blocklist`, `must_state`) still block. The agent fails if the proxy is unreachable — this is intentional: if you set the env var, you want enforcement.

---

### Can I run multiple contracts?

v0.4: one contract per proxy process. Run multiple proxies on different ports for different contracts. v0.5 will add per-route contract loading (`?contract=foo.yaml`).

---

### Does the proxy store my API keys?

No. API keys pass through as HTTP headers. The proxy never logs or stores them.

---

### What's the difference between hard and soft violations?

Hard violations (`tool_blocklist`, `tool_allowlist`, `must_state`, `context_budget` with `deny`) block the request immediately with a `ContractBreachError`. Soft violations (`must_precede`, `process_drift`, `judge_predicate`) are recorded and may apply Θ penalties but don't block the agent.

---

### What is Θ (Theta)?

Θ is the reliability score for an agent session. It's a weighted metric (0–1) combining compliance rate, drift level, event frequency, and recovery success. Think of it as a health score for your agent's behavioral contract adherence. Default deployment threshold: Θ ≥ 0.90.

---

### How does drift detection work?

Jensen-Shannon divergence (JSD) compares your agent's current action distribution against a frozen baseline. If the distribution shifts significantly (e.g., agent starts using `Bash` 80% of the time instead of 30%), JSD rises. Configure the threshold and action (log/warn/theta_penalty) in your contract.

---

### What is the judge predicate?

An LLM-as-judge that evaluates qualitative rules on a sample of turns. Example: "Does the response show L99 conviction?" The judge runs asynchronously on 20% of turns using a cheap model (DS Flash:free, $0). Failed evaluations apply Θ penalties.

---

### Can I write my own contracts?

Yes. The contract DSL is YAML. See [Contract DSL Reference](contracts.md) for the full schema. Start from one of the three templates (`safety-minimal`, `partner-mode`, `full-governance`).

---

### Is this open source?

Yes — MIT License. Core kernel and all adapters are fully open source. [Licensing details](licensing.md).

---

### How do I report a bug?

[GitHub Issues](https://github.com/qualixar/agentassert-typec/issues). Include: contract YAML, agent configuration, and the violation log if applicable.

---

### When is v0.5 shipping?

v0.5 adds LiteLLM `async_pre_call_hook` middleware, multi-tenant proxy, and hot-reload atomic swap. Target: +3 weeks from v0.4 GA. See [Roadmap](roadmap.md).

---

### How do I get commercial support?

Email: varun.pratap.bhardwaj@gmail.com. See [Licensing](licensing.md) for enterprise options.

---

### What's the academic backing?

The paper ["Formal Behavioral Contracts for AI Agents"](https://arxiv.org/abs/2602.22302) (arXiv:2602.22302) defines the mathematical framework: JSD drift, (p, δ, k)-satisfaction, Θ reliability scoring, and Lyapunov stability analysis.

---

### How does this relate to AgentAssert ABC?

ABC is the research/enterprise product for multi-agent formal governance. Type-C is the developer wedge — same kernel, same math, `pip install` + env-var swap. Type-C users can upgrade to ABC for multi-agent contracts.

---

### Does Type-C work with LiteLLM?

v0.4: use the HTTP proxy (`OPENAI_BASE_URL=http://localhost:9000/openai`). v0.5: native `async_pre_call_hook` middleware integration — one config line in LiteLLM, auto-covers AutoGen, ADK, DeerFlow, and LangChain users of LiteLLM.
