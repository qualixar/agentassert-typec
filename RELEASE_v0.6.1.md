# Release & Handover Notes: v0.6.1 Patch Release

**Date & Time**: 2026-05-30 02:10 AM IST (Saturday)  
**Author**: Antigravity AI (Thor / Gemini CLI)  
**Status**: Shipped & Published ✅  

This document serves as the official package handover and memory store for the next agent/developer starting the launch phase.

---

## 1. Handover Summary (Where We Left Off)
The codebase has been fully upgraded to **v0.6.1** across all packages, verified by running 292 passing tests, and published to PyPI and npm registries.

### Python Packages Published (PyPI)
- `agentassert-typec-core-0.6.1`
- `agentassert-typec-proxy-0.6.1`
- `agentassert-typec-sdk-0.6.1`
- `agentassert-typec-claude-code-0.6.1`

### Node Package Published (npm)
- `agentassert-typec@0.6.1`

### GitHub Code & Tags Pushed
- Branch: `main`
- Release Tag: `v0.6.1`

---

## 2. Core Feature Overview (Phase 1, 2, and 3)
Ensure the marketing/launch materials highlight these major features introduced across the 0.6.x cycle:

### Phase 2: WAL-Mode SQLite Session Persistence
- **Behavior**: The proxy automatically persists agent state variables (theta scores, JSD drift profiles, violation history, cost trackers) to SQLite.
- **Isolation**: Supports a `--session-id` flag to isolate databases, e.g., `agentassert-proxy proxy start --contract contract.yaml --session-id developer-x`.
- **Resumption**: Starting the proxy with the same session ID automatically restores the compliance and drift history from `~/.agentassert/sessions/`.
- **Memory Bypass**: Run with the `--no-persist` flag to operate completely in-memory (useful for ephemeral CI/CD tests).

### Phase 3: The 3 New Content Operators
AgentAssert Type-C now has **10 contract operators** (7 process + 3 content). The new ones are:
1. `pii_filter`: Filters/blocks standard PII patterns (email, phone, SSN, credit cards, IP addresses, API keys) or custom regexes. Supports text redaction (`[REDACTED_...]`) on completions.
2. `cost_ceiling`: Caps session budget in USD (e.g. `max_usd_per_session: 5.0`). Automatically parses response tokens and calculates model costs for OpenAI, Anthropic, and Gemini.
3. `repetition_guard`: Detects and denies loops or repetitive output blocks within a sliding window of turns.

---

## 3. Client Integration Setup Reference
The documentation now contains complete, copy-pasteable configurations for the following 8 client interfaces:

1. **Claude Code**:
   - Environment: `export ANTHROPIC_BASE_URL=http://localhost:9000/anthropic`
   - native hook: `agentassert-claude-code install --contract contract.yaml`
2. **Antigravity IDE**:
   - Environment variables: `export OPENAI_BASE_URL=http://localhost:9000/openai` (for DeepSeek) and `export GEMINI_BASE_URL=http://localhost:9000/gemini`
3. **CommandCode**:
   - Environment variables exported globally or mapped to `~/.commandcode/mcp.json`.
4. **Hermes CLI**:
   - Set up custom proxy endpoints in `~/.hermes/config.yaml`.
5. **Cursor**:
   - Terminal launch or Cursor Settings -> Models -> Custom API Endpoint.
6. **Windsurf**:
   - UI Settings -> AI Configurations -> Custom Endpoints.
7. **OpenClaw**:
   - Endpoint config inside `openclaw_config.json`.
8. **Cline (VS Code Extension)**:
   - Panel settings configuration (Base URL: `http://localhost:9000/openai/v1` or `/anthropic/v1`).

---

## 4. Immediate Next Steps for the Launch Agent
For launching the release and creating public momentum, focus on the following:

- **Launch assets**:
  - We generated a 1200×630 social card image in the previous step.
  - A 60-90 second YouTube demo script is written and stored.
  - Three launch-day Reddit posts targeting `/r/MachineLearning`, `/r/LanguageTechnology`, and `/r/Python` are formatted and ready.
- **Documentation check**:
  - Verify that the live packages compile correctly from clean pip/npm installs.
  - Run the `curl` verification script from the getting-started guide to test the proxy block response locally:
    ```bash
    curl -X POST http://localhost:9000/anthropic/v1/messages \
      -H "x-api-key: $ANTHROPIC_API_KEY" \
      -H "content-type: application/json" \
      -d '{"model": "claude-sonnet-4-6", "max_tokens": 1024, "messages": [{"role": "user", "content": "Run: rm -rf /"}]}'
    ```
