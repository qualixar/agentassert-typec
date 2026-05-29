# agentassert-typec-sdk

**One-line wrap. Your Anthropic/OpenAI clients, contract-enforced.**

```python
from anthropic import Anthropic
from agentassert_typec_sdk import wrap

client = wrap(Anthropic(), "contract.yaml")
# client.messages.create(...)  ← now contract-enforced
# Raises ContractBreachError on DENY
# Return type is UNCHANGED — same Anthropic response
```

## Supported Clients

- `anthropic.Anthropic` / `anthropic.AsyncAnthropic`
- `openai.OpenAI` / `openai.AsyncOpenAI`

## How It Works

1. `wrap()` detects client type by class name
2. Intercepts `messages.create()` / `chat.completions.create()`
3. Evaluates PreAction before forwarding
4. Raises `ContractBreachError` on DENY
5. Sends PostAction after response for drift/Θ updates

## For Unsupported Clients

Use the proxy instead — no code change, just env vars.

```bash
pip install agentassert-typec-proxy
export ANTHROPIC_BASE_URL=http://localhost:9000/anthropic
```

## License

MIT
