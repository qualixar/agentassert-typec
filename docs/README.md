# AgentAssert Type-C Documentation

Welcome to the official documentation for AgentAssert Type-C v0.4.

## Quick Links

- **[Getting Started](getting-started.md)** — Install and set up in 5 minutes
- **[Contract DSL Reference](contracts.md)** — All 7 process operators
- **[HTTP Proxy Guide](proxy.md)** — Zero-code integration
- **[API Reference](api-reference.md)** — Python SDK API

## What Is Type-C?

AgentAssert Type-C enforces formal behavioral contracts on AI agents at runtime. It sits between your agent and any LLM API — blocking dangerous tool calls, detecting behavioral drift, capping token usage, and running LLM-as-judge quality evaluations.

**"Set one env var. Get formal behavioral contracts on any agent, any model, any framework."**

## Documentation Map

| Section | What You'll Find |
|---|---|
| [Getting Started](getting-started.md) | All 4 install paths, quickstart, verification |
| [Contract DSL Reference](contracts.md) | Complete YAML schema for all 7 process operators |
| [HTTP Proxy Guide](proxy.md) | Flagship integration — start, configure, test, Docker |
| [Python SDK Guide](sdk.md) | One-line `wrap()` for Anthropic/OpenAI SDKs |
| [Claude Code Hook Guide](claude-code.md) | Zero-code hook for Claude Code CLI |
| [Architecture](architecture.md) | Package layout, event protocol, enforcement flow |
| [Mathematics](math.md) | JSD drift, Θ scorer, (p,δ,k) framework |
| [API Reference](api-reference.md) | Full Python API for `agentassert-typec-core` |
| [Case Study](case-study.md) | CLAUDE.md compression: 48% reduction |
| [FAQ](faq.md) | Common questions |
| [Licensing](licensing.md) | MIT terms, commercial support |

## Repository

[github.com/qualixar/agentassert-typec](https://github.com/qualixar/agentassert-typec)

## Paper

[arXiv:2602.22302 — "Formal Behavioral Contracts for AI Agents"](https://arxiv.org/abs/2602.22302)
