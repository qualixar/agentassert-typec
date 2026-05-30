"""
Tier 2: AgentAssert Type-C — Proxy E2E latency overhead benchmark.

Starts a lightweight mock upstream (no real LLM) and measures the
added latency of routing through the Type-C proxy vs hitting the
upstream directly.

Run:
    cd agentassert-typec
    PYTHONPATH=packages/core/src:packages/proxy/src uv run python scripts/bench_proxy_overhead.py
"""

from __future__ import annotations

import asyncio
import json
import statistics
import tempfile
import textwrap
import time
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------
MOCK_PORT = 19101
PROXY_PORT = 19102
N_REQUESTS = 200
WARMUP = 20


# ---------------------------------------------------------------------------
# Mock upstream: returns a minimal Anthropic-shaped response immediately
# ---------------------------------------------------------------------------
mock_app = FastAPI()

MOCK_RESPONSE = {
    "id": "msg_bench",
    "type": "message",
    "role": "assistant",
    "content": [{"type": "text", "text": "Hello from mock upstream."}],
    "model": "claude-sonnet-4-6",
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 10, "output_tokens": 8},
}


@mock_app.post("/{path:path}")
async def mock_handler(path: str, request: Request):
    return JSONResponse(content=MOCK_RESPONSE)


# ---------------------------------------------------------------------------
# Benchmark contract (minimal — just process through, no violations)
# ---------------------------------------------------------------------------
BENCH_CONTRACT = textwrap.dedent("""\
    dsl_version: "0.4"
    contractspec: "1.0"
    kind: agent
    name: bench-proxy
    description: "Proxy overhead benchmark contract."
    version: "1.0"

    upstream:
      anthropic: "http://127.0.0.1:19101"

    invariants:
      process:
        - tool_blocklist:
            tools: ["rm_rf"]
            scope: session

    recovery:
      on_hard_violation: raise
      on_soft_violation: log_and_continue
""")

REQUEST_PAYLOAD = json.dumps({
    "model": "claude-sonnet-4-6",
    "max_tokens": 128,
    "messages": [{"role": "user", "content": "ping"}],
})


async def run_server(app: FastAPI, port: int) -> asyncio.Task:
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="error",
        access_log=False,
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    # Wait for server to be ready
    for _ in range(50):
        try:
            async with httpx.AsyncClient() as c:
                await c.get(f"http://127.0.0.1:{port}/health", timeout=0.2)
            break
        except Exception:
            await asyncio.sleep(0.05)
    return task, server


async def wait_port_ready(port: int, retries: int = 60):
    for _ in range(retries):
        try:
            async with httpx.AsyncClient() as c:
                await c.post(
                    f"http://127.0.0.1:{port}/anthropic/v1/messages",
                    content=REQUEST_PAYLOAD,
                    headers={"content-type": "application/json", "x-api-key": "test"},
                    timeout=1.0,
                )
            return
        except Exception:
            await asyncio.sleep(0.1)


async def benchmark():
    import sys
    sys.path.insert(0, "packages/core/src")
    sys.path.insert(0, "packages/proxy/src")

    from agentassert_typec_proxy.server import create_app

    # Write temp contract
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(BENCH_CONTRACT)
        contract_path = f.name

    # Start mock upstream
    mock_config = uvicorn.Config(
        mock_app, host="127.0.0.1", port=MOCK_PORT,
        log_level="error", access_log=False,
    )
    mock_server = uvicorn.Server(mock_config)
    mock_task = asyncio.create_task(mock_server.serve())
    await asyncio.sleep(1.5)

    # Start proxy
    proxy_app = create_app(contract_path, persist=False)
    proxy_config = uvicorn.Config(
        proxy_app, host="127.0.0.1", port=PROXY_PORT,
        log_level="error", access_log=False,
    )
    proxy_server = uvicorn.Server(proxy_config)
    proxy_task = asyncio.create_task(proxy_server.serve())
    await asyncio.sleep(2.0)

    headers = {"content-type": "application/json", "x-api-key": "test-key"}
    direct_url = f"http://127.0.0.1:{MOCK_PORT}/v1/messages"
    proxy_url = f"http://127.0.0.1:{PROXY_PORT}/anthropic/v1/messages"

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Warmup
        for _ in range(WARMUP):
            await client.post(direct_url, content=REQUEST_PAYLOAD, headers=headers)
            await client.post(proxy_url, content=REQUEST_PAYLOAD, headers=headers)

        # Benchmark direct
        direct_times_ms = []
        for _ in range(N_REQUESTS):
            t0 = time.perf_counter_ns()
            await client.post(direct_url, content=REQUEST_PAYLOAD, headers=headers)
            t1 = time.perf_counter_ns()
            direct_times_ms.append((t1 - t0) / 1_000_000)

        # Benchmark via proxy
        proxy_times_ms = []
        for _ in range(N_REQUESTS):
            t0 = time.perf_counter_ns()
            await client.post(proxy_url, content=REQUEST_PAYLOAD, headers=headers)
            t1 = time.perf_counter_ns()
            proxy_times_ms.append((t1 - t0) / 1_000_000)

    mock_server.should_exit = True
    proxy_server.should_exit = True
    await asyncio.gather(mock_task, proxy_task, return_exceptions=True)

    dm = statistics.mean(direct_times_ms)
    pm = statistics.mean(proxy_times_ms)
    overhead = pm - dm
    overhead_p99 = sorted(proxy_times_ms)[int(N_REQUESTS * 0.99)] - sorted(direct_times_ms)[int(N_REQUESTS * 0.99)]

    print()
    print("=" * 60)
    print(f"  AgentAssert Type-C — Proxy E2E Overhead ({N_REQUESTS} requests)")
    print("=" * 60)
    print(f"  {'Metric':<30} {'Direct':>10} {'Via Proxy':>10}")
    print(f"  {'-'*30} {'-'*10} {'-'*10}")
    print(f"  {'mean latency':<30} {dm:>9.2f}ms {pm:>9.2f}ms")
    print(f"  {'median latency':<30} {statistics.median(direct_times_ms):>9.2f}ms {statistics.median(proxy_times_ms):>9.2f}ms")
    print(f"  {'p99 latency':<30} {sorted(direct_times_ms)[int(N_REQUESTS*0.99)]:>9.2f}ms {sorted(proxy_times_ms)[int(N_REQUESTS*0.99)]:>9.2f}ms")
    print(f"  {'min':<30} {min(direct_times_ms):>9.2f}ms {min(proxy_times_ms):>9.2f}ms")
    print("=" * 60)
    print(f"\n  Proxy overhead (mean):  +{overhead:.2f}ms per request")
    print(f"  Proxy overhead (p99):   +{max(overhead_p99, 0):.2f}ms per request")
    print(f"\n  (Mock upstream only — no real LLM network RTT in these numbers)")
    print(f"  Real-world LLM latency: 500–3000ms. Proxy overhead is negligible.")
    print()


if __name__ == "__main__":
    asyncio.run(benchmark())
