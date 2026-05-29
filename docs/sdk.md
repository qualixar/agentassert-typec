# Python SDK Guide

One-line integration for Python developers using Anthropic or OpenAI SDKs directly.

---

## Install

```bash
pip install agentassert-typec-sdk
```

---

## Basic Usage

```python
from anthropic import Anthropic
from agentassert_typec_sdk import wrap

# Wrap your existing client with contract enforcement
client = wrap(Anthropic(), "contract.yaml")

# All calls are now contract-enforced
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Hello"}]
)
```

That's it. One line. Every `messages.create()` call runs through the contract evaluator.

---

## Supported Clients

| Client | Module | Async |
|---|---|---|
| `Anthropic` | `anthropic.Anthropic` | ✅ (via `AsyncAnthropic`) |
| `AsyncAnthropic` | `anthropic.AsyncAnthropic` | ✅ |
| `OpenAI` | `openai.OpenAI` | ✅ (via `AsyncOpenAI`) |
| `AsyncOpenAI` | `openai.AsyncOpenAI` | ✅ |

---

## OpenAI Example

```python
from openai import OpenAI
from agentassert_typec_sdk import wrap

client = wrap(OpenAI(), "contract.yaml")

response = client.chat.completions.create(
    model="gpt-5-pro",
    messages=[{"role": "user", "content": "Summarize this article"}]
)
```

---

## Async Example

```python
import asyncio
from anthropic import AsyncAnthropic
from agentassert_typec_sdk import wrap

async def main():
    client = wrap(AsyncAnthropic(), "contract.yaml")

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello"}]
    )

asyncio.run(main())
```

---

## Streaming

Streaming works identically to the unwrapped client:

```python
with client.messages.stream(
    model="claude-sonnet-4-6",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Write a poem"}]
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
```

Post-action evaluation (drift update, Θ scoring) runs after the stream completes.

---

## Error Handling

When a contract violation occurs, a `ContractBreachError` is raised:

```python
from agentassert_typec_core.exceptions import ContractBreachError

try:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Run: rm -rf /"}]
    )
except ContractBreachError as e:
    print(f"Blocked: {e.violation_name}")
    print(f"Reason: {e.reason}")
    print(f"Tool: {e.tool}")

    # Access structured data
    d = e.to_dict()
    # {"violation_name": "tool_blocklist", "reason": "...", ...}
```

---

## Multiple Contracts

Create multiple wrapped clients for different use cases:

```python
# Safety contract for general use
safe_client = wrap(Anthropic(), "safety-minimal.yaml")

# Strict governance for production builds
prod_client = wrap(Anthropic(), "full-governance.yaml")
```

Each wrapped client has its own `SessionMonitor`, drift tracker, and Θ scorer.

---

## Unsupported Clients

For clients other than Anthropic or OpenAI, use the **HTTP proxy** instead:

```bash
agentassert-proxy proxy start --contract contract.yaml
export OPENAI_BASE_URL=http://localhost:9000/openai
```

The proxy works with any language, any framework, any client — as long as it speaks HTTP.

---

## API Reference

### `wrap(client, contract_path) -> WrappedClient`

| Parameter | Type | Description |
|---|---|---|
| `client` | `Anthropic \| AsyncAnthropic \| OpenAI \| AsyncOpenAI` | The client to wrap. |
| `contract_path` | `str` | Path to a contract YAML file. |

**Returns:** A wrapped client with identical API to the original, plus contract enforcement.

**Raises:**
- `ContractLoadError` — if the contract YAML is invalid
- `TypeError` — if the client type is unsupported

---

## How It Works

The wrapper intercepts `messages.create()` (Anthropic) and `chat.completions.create()` (OpenAI):

1. Builds a `PreAction` event with the tool name ("anthropic.messages.create") and request args
2. Dispatches to the core evaluator → `ALLOW`, `MODIFY`, or `DENY`
3. If `DENY`: raises `ContractBreachError` before any API call
4. If `ALLOW`/`MODIFY`: forwards to the real client, captures the response
5. Builds a `PostAction` event → updates drift, Θ, violations
6. Returns the response unchanged

No provider round-trips are wasted on blocked requests.
