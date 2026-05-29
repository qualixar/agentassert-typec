# HTTP Proxy Guide

The proxy is the flagship integration. It sits between your agent and the LLM provider, enforcing contracts at the HTTP level with zero code changes.

---

## Install

```bash
pip install agentassert-typec-proxy
```

Other options:

```bash
# npm (Node.js ecosystem)
npx agentassert-typec proxy start --contract contract.yaml

# Homebrew (macOS)
brew install agentassert-typec
```

---

## Start the Proxy

```bash
agentassert-proxy proxy start --contract contract.yaml --port 9000 --host 127.0.0.1
```

| Flag | Default | Description |
|---|---|---|
| `--contract`, `-c` | *(required)* | Path to contract YAML file |
| `--port`, `-p` | `9000` | Port to listen on |
| `--host`, `-h` | `127.0.0.1` | Host to bind to |

---

## Configure Your Agent

Set provider base URLs to point at the proxy:

```bash
export ANTHROPIC_BASE_URL=http://localhost:9000/anthropic
export OPENAI_BASE_URL=http://localhost:9000/openai
export GEMINI_BASE_URL=http://localhost:9000/gemini
export OPENROUTER_BASE_URL=http://localhost:9000/openrouter
```

Your API keys continue to be passed through as headers — the proxy doesn't store or log them.

---

## Supported Providers

| Provider | Endpoint | What's Forwarded |
|---|---|---|
| **Anthropic** | `POST /anthropic/v1/messages` | Messages API |
| **Anthropic** | `POST /anthropic/v1/messages/count_tokens` | Token counting (passthrough) |
| **OpenAI** | `POST /openai/v1/chat/completions` | Chat Completions API |
| **Gemini** | `POST /gemini/v1/models/{model}:generateContent` | Gemini generation |
| **OpenRouter** | `POST /openrouter/v1/chat/completions` | OpenRouter relay |

All standard headers (`Authorization`, `x-api-key`, `anthropic-version`, etc.) are forwarded transparently.

---

## Enforcement Flow

For every request:

1. **Parse** — Extract tool calls from the provider-specific wire format
2. **Normalize** — Convert to canonical `CanonicalRequest` representation
3. **Evaluate** — Run against compiled contract predicates (AST-cached, compiled once at startup)
4. **Decide** — `ALLOW` (forward), `MODIFY` (forward with changed payload), or `DENY` (block with error)
5. **Update** — Post-response: update JSD distribution, Θ score, violation log

```
Client → Proxy (enforce) → Provider → Proxy (update) → Client
```

---

## Streaming

Streaming responses (`stream: true`) use **Option B** — stream-through with post-stream Θ update.

- Tokens flow to the client without buffering
- Drift and Θ are updated after the stream completes
- No inline enforcement on streamed output (v0.4; v0.5 may add mid-stream termination)

---

## Hot Reload

Edit `contract.yaml` while the proxy is running — it picks up changes automatically.

- File watcher polls every 500ms via SHA256 comparison
- On change: compiles new contract, swaps atomically on the next request
- If the new contract is invalid: keeps the old contract, logs warning
- No in-flight requests are broken

---

## Endpoints

| Path | Description |
|---|---|
| `GET /health` | Health check — returns JSON status |
| `GET /status` | Proxy status — contract, uptime, sessions |
| `POST /admin/reload` | Force contract reload from disk |

```bash
# Check proxy health
curl http://localhost:9000/health

# Check proxy status
curl http://localhost:9000/status

# Check from CLI
agentassert-proxy proxy status --port 9000
```

---

## Latency Budget

| Stage | p99 Budget |
|---|---|
| HTTP parse + normalize | 2ms |
| Predicate evaluation | 10ms |
| Provider forwarding | (provider RTT) |
| PostAction state extraction | 5ms |
| JSD distribution update | 8ms |
| Θ computation | 3ms |
| HTTP response write | 2ms |
| **Total proxy overhead** | **< 30ms** |

Predicate AST is compiled once at `SessionStart` and cached — never reparsed per request. JSD is incremental (Welford-style, O(1) per update). LLM-as-judge predicates run async/sampled, not inline.

---

## Testing Locally

Test that blocked tools are actually blocked:

```bash
# Start proxy with safety-minimal contract
agentassert-proxy proxy start --contract safety-minimal.yaml

# This should be BLOCKED (rm -rf is in blocklist)
curl -X POST http://localhost:9000/anthropic/v1/messages \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{
    "model": "claude-sonnet-4-6",
    "max_tokens": 1024,
    "messages": [{"role": "user", "content": "Run: rm -rf /"}]
  }'

# Expected: 400 with ContractBreachError JSON
```

Response from a blocked request:

```json
{
  "error": "ContractBreachError",
  "violation": "tool_blocklist",
  "reason": "Tool 'Bash' matches blocklisted pattern 'rm -rf /*'",
  "tool": "Bash",
  "session_id": "safety-minimal",
  "contract_id": "safety-minimal"
}
```

---

## Docker

A multi-stage Dockerfile is included at `packages/proxy/src/agentassert_typec_proxy/dist/Dockerfile`.

```bash
docker build -t agentassert-proxy -f packages/proxy/src/agentassert_typec_proxy/dist/Dockerfile .
docker run -p 9000:9000 -v $(pwd)/contract.yaml:/contract.yaml agentassert-proxy
```

---

## Limitations (v0.4)

- **Single contract per proxy process.** Multi-tenant (per-route contract loading) ships in v0.5.
- **No gRPC / non-HTTP protocols.** Proxy speaks HTTP/1.1 and HTTP/2.
- **Streaming enforcement is post-stream only.** Mid-stream termination ships in v0.5+.
- **No built-in auth on proxy endpoints.** Keep proxy on localhost. Add reverse proxy (nginx/Caddy) for remote access.
