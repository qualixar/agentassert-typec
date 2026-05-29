# Changelog

All notable changes to AgentAssert Type-C will be documented in this file.

---

## [0.6.1] - 2026-05-30

### Added
- **Comprehensive Integration Documentation**:
  - Detailed step-by-step config guides for modern AI coding tools and agents:
    - **Claude Code**: Environment variables and native hook integration.
    - **Antigravity IDE**: Proxy interception for DeepSeek and Gemini.
    - **CommandCode**: Global MCP (`~/.commandcode/mcp.json`) proxy configuration.
    - **Hermes CLI**: Upstream configuration via `~/.hermes/config.yaml`.
    - **Cursor & Windsurf**: Setup via environment variables and Custom API Endpoint fields.
    - **OpenClaw & Cline**: Base URL routing.
- **Contract DSL & Content Operators Documentation**:
  - Full schema, parameter list, and default values for Phase 3 content operators: `pii_filter`, `cost_ceiling`, and `repetition_guard`.
- **Session Persistence Reference**:
  - Full instructions on using sqlite persistence, isolating sessions via `--session-id`, turning persistence off via `--no-persist`, and analyzing proxy state via updated `/health` and `/status` endpoints.

---

## [0.6.0] - 2026-05-29

### Added
- **SQLite Session Persistence (Phase 2)**:
  - Added automatic WAL-mode SQLite database creation under `~/.agentassert/sessions/` named after the contract slug.
  - Support for persisting state variables across proxy restarts: JSD drift distributions, $\Theta$ reliability score, violations history, cost, and repetition counters.
  - Added uvicorn lifespan hook to flush states and safely close the sqlite database.
  - Added CLI options to `agentassert-proxy start`: `--session-id` (`-s`) to isolate databases, and `--no-persist` to run in memory.
  - Added persistence status block to `/health` endpoint.
- **Content Operators (Phase 3)**:
  - `pii_filter`: Enforces PII detection (SSN, Email, Phone, CreditCard, IP, etc.) with configurable actions (`redact` or `warn`).
  - `cost_ceiling`: Caps the total session dollar spend. Monitors usage stats from OpenAI, Anthropic, and Gemini response metadata.
  - `repetition_guard`: Detects and warns or blocks repetitive loops in assistant responses.
  - Added cost metadata block to `/status` endpoint (percentage used, remaining budget, accumulated USD).
- **Streaming Support for Operators**:
  - Enforced cost ceilings and warning-only rules on SSE/streaming messages.
- **Test Coverage**:
  - Added 50+ unit and integration tests across packages/core and packages/proxy.
