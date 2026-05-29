# Architecture

AgentAssert Type-C is a 4-package system with a pure Python kernel and three integration adapters.

---

## Package Architecture

```
                ┌──────────────────────────────────────────────┐
                │       agentassert-typec-core (kernel)        │
                │  • ContractSpec DSL parser + validator       │
                │  • Predicate AST compiler (regex cache)      │
                │  • 7-operator process evaluator              │
                │  • JSD drift detector (Welford incremental)  │
                │  • Θ reliability scorer                      │
                │  • (p, δ, k) satisfaction monitor            │
                │  • Violation log (thread-safe)               │
                │  • Judge dispatcher (async, sampled)         │
                │  • OTel exporter (fire-and-forget)           │
                │                                              │
                │  Deps: pydantic, numpy, scipy, ruamel-yaml   │
                │  NO LLM deps. NO HTTP deps.                  │
                └──────────────────┬───────────────────────────┘
                                   │ imported by ↓
        ┌──────────────────┬───────┴───────┬────────────────────┐
        │                  │               │                    │
┌───────▼──────────┐ ┌─────▼─────┐ ┌───────▼────────┐ ┌─────────▼────────┐
│ typec-proxy      │ │ typec-sdk │ │ typec-claude-  │ │ typec-litellm    │
│ (FLAGSHIP)       │ │           │ │ code           │ │ (v0.5)           │
│                  │ │           │ │                │ │                  │
│ HTTP forwarder   │ │ wrap(c)   │ │ hook adapter   │ │ pre_call_hook    │
│ FastAPI + uvicorn│ │ for       │ │ for Claude     │ │ for AutoGen +    │
│ + httpx          │ │ direct    │ │ Code CLI       │ │ ADK + DeerFlow   │
│                  │ │ SDK use   │ │                │ │ + LangChain      │
└──────────────────┘ └───────────┘ └────────────────┘ └──────────────────┘
```

**Key property:** Core is provider-blind and transport-blind. It accepts canonical events from any adapter and returns canonical decisions. All wire-format / SDK-format / hook-format translation lives in the adapter packages.

---

## Core Kernel (`agentassert-typec-core`)

### Modules

| Module | Purpose |
|---|---|
| `models/contract.py` | 17 Pydantic models: ContractSpecExtended, 7 process operators, ABC v0.3 compat |
| `models/events.py` | 7 TypeCEvent dataclasses (PreAction, PostAction, TurnStart, TurnEnd, SessionStart, SessionEnd, ContextWindow) |
| `models/decisions.py` | TypeCDecision enum (ALLOW/MODIFY/DENY), DecisionResult |
| `models/session.py` | SessionContext, HistoryDigest, DriftReport |
| `dsl/parser.py` | `parse_contract(path)` → ParseResult with dsl_version compat |
| `dsl/validator.py` | `validate_extended(data)` → all 7 operators validated |
| `dsl/ast_compiler.py` | `CompiledContract.from_spec()` — regex pre-compilation once per session |
| `evaluator/engine.py` | `dispatch_event()` — routes 7 events to correct evaluators |
| `evaluator/process_eval.py` | Per-operator evaluators (blocklist, must_state, context_budget, drift, precede) |
| `evaluator/operators.py` | ABC v0.3 constraint bridge |
| `monitor/session.py` | `SessionMonitor` — from_yaml, evaluate, close, schedule_judge_evaluation |
| `monitor/drift.py` | `DriftTracker` — Welford-style incremental JSD (O(1) per update) |
| `monitor/theta.py` | `ThetaScorer` — Θ = 0.35C̄ + 0.25(1-D̄) + 0.20/(1+E) + 0.20S |
| `monitor/violation_log.py` | `ViolationLog` — thread-safe, deque(maxlen=1000) |
| `judge/dispatcher.py` | `JudgeDispatcher` — cost-ceiling, sample-rate gate, DS Flash:free + Haiku routing |
| `exporters/otel.py` | `TypeCOTelExporter` — fire-and-forget queue, background drain |
| `exceptions.py` | ContractBreachError (to_http_body), ContractLoadError, PredicateEvalError |

---

## HTTP Proxy (`agentassert-typec-proxy`)

The flagship integration. FastAPI server that intercepts HTTP requests before they reach the provider.

```bash
agentassert-proxy proxy start --contract contract.yaml --port 9000
```

### Request Flow

```
Client                              Proxy                              Provider
  │                                    │                                   │
  │  POST /anthropic/v1/messages       │                                   │
  │ ──────────────────────────────────>│                                   │
  │                                    │  1. Parse Anthropic wire format   │
  │                                    │  2. Normalize → CanonicalRequest  │
  │                                    │  3. Build PreAction event         │
  │                                    │  4. Evaluate → ALLOW/DENY/MODIFY │
  │                                    │                                   │
  │                                    │  If DENY:                         │
  │  400 + ContractBreachError        │ ──────────────────────────────    │
  │ <──────────────────────────────────│                                   │
  │                                    │                                   │
  │                                    │  If ALLOW/MODIFY:                 │
  │                                    │  POST /v1/messages (forward)     │
  │                                    │ ─────────────────────────────────>│
  │                                    │                          Response │
  │                                    │ <─────────────────────────────────│
  │                                    │  5. Build PostAction event        │
  │                                    │  6. Update JSD, Θ, violations     │
  │  Response                          │                                   │
  │ <──────────────────────────────────│                                   │
```

### Modules

| Module | Purpose |
|---|---|
| `normalizer/canonical.py` | CanonicalRequest, CanonicalToolCall, CanonicalResponse |
| `normalizer/anthropic_norm.py` | Anthropic messages → CanonicalRequest |
| `normalizer/openai_norm.py` | OpenAI chat/completions → CanonicalRequest |
| `normalizer/gemini_norm.py` | Gemini generateContent → CanonicalRequest |
| `normalizer/openrouter_norm.py` | OpenRouter chat/completions → CanonicalRequest |
| `routes/anthropic.py` | `POST /v1/messages`, `POST /v1/messages/count_tokens` |
| `routes/openai.py` | `POST /v1/chat/completions` |
| `routes/gemini.py` | `POST /v1/models/{model}:generateContent` |
| `routes/openrouter.py` | `POST /v1/chat/completions` |
| `enforcement.py` | `enforce_and_forward()` — normalize → evaluate → DENY/forward |
| `forwarder.py` | httpx.AsyncClient singleton, header forwarding |
| `hot_reload.py` | ContractWatcher — SHA256 poll (500ms), atomic swap |
| `server.py` | `create_app()` — FastAPI with lifespan, health/status/admin endpoints |
| `cli.py` | Click CLI: `proxy start`, `proxy status` |

---

## Type-C Event Protocol (7 Events)

Every adapter translates its native event surface into these seven canonical events. This is the moat — if translation requires > 200 LOC per adapter, the protocol is wrong.

| Event | When | What It Carries |
|---|---|---|
| `PreAction` | Before tool invocation | tool name, args, session context |
| `PostAction` | After tool returns | tool, args, result, extracted state |
| `TurnStart` | User turn begins | user input, history summary |
| `TurnEnd` | Assistant turn completes | output, state delta |
| `SessionStart` | Agent/session boots | workdir, model, config |
| `SessionEnd` | Agent/session closes | final Θ score, drift report |
| `ContextWindow` | Per-turn context measurement | token count, prefix hash |

### 3 Canonical Decisions

| Decision | Meaning |
|---|---|
| `ALLOW` | Forward unchanged |
| `MODIFY` | Forward with mutated payload |
| `DENY` | Block, return contract-defined error |

---

## Hot Reload

The file watcher polls `contract.yaml` every 500ms. On change:

1. Reads new YAML
2. Validates against schema
3. Compiles AST
4. Atomically swaps the `CompiledContract` reference under `RLock`

If the new contract is invalid, the old contract stays active. No in-flight requests are disrupted.

---

## Streaming (v0.4)

Uses **Option B** — stream-through with post-stream Θ update.

- Provider response bytes are forwarded to client as they arrive (no buffering)
- After the stream completes, PostAction evaluation runs (drift update, Θ scoring)
- No inline enforcement on streaming chunks (v0.5 may add mid-stream termination for safety-critical contracts)

---

## Latency Budget

| Stage | p99 Budget | Mechanism |
|---|---|---|
| HTTP parse + normalize | 2ms | uvloop + orjson |
| Predicate eval | 10ms | AST-cached, regex pre-compiled |
| Provider RTT | (not counted) | passthrough |
| PostAction extraction | 5ms | JSON path, lazy |
| JSD update | 8ms | Welford incremental, O(1) |
| Θ computation | 3ms | windowed metric |
| Response write | 2ms | streaming pass-through |
| **Total overhead** | **< 30ms** | hard constraint |

---

## Thread Safety

- `SessionMonitor.evaluate()` is protected by `threading.RLock`
- `ViolationLog` uses `threading.Lock` on write
- `DriftTracker` state is mutated under the same RLock
- Judge dispatchers run async, off the hot path
