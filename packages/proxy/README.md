# agentassert-typec-proxy

**HTTP forwarding proxy — formal behavioral contracts middleware with zero code change.**

This is the flagship. Drop it between any agent harness and any LLM API. Set one env var. Done.

## Quickstart

```bash
pip install agentassert-typec-proxy
agentassert-proxy proxy start --contract contract.yaml
```

Then in your agent environment:
```bash
export ANTHROPIC_BASE_URL=http://localhost:9000/anthropic
export OPENAI_BASE_URL=http://localhost:9000/openai
```

## Supported Providers

| Provider | Route Prefix | Env Var |
|---|---|---|
| Anthropic | `/anthropic` | `ANTHROPIC_BASE_URL` |
| OpenAI | `/openai` | `OPENAI_BASE_URL` |
| Gemini | `/gemini` | `GEMINI_BASE_URL` |
| OpenRouter | `/openrouter` | `OPENROUTER_BASE_URL` |

## Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check, returns contract name and Θ |
| `GET` | `/status` | Full status: Θ, JSD, violation count |
| `POST` | `/admin/reload` | Trigger contract hot-reload |

## Performance

- p99 overhead < 30ms (excluding provider RTT)
- All regex patterns pre-compiled at startup
- Hot-reload via SHA256 file polling (500ms interval)
- Fail-safe: invalid contract → keeps old monitor

## License

MIT
