from __future__ import annotations

import os

import httpx
from fastapi import Request

_PROVIDER_DEFAULTS: dict[str, str] = {
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com",
    "gemini": "https://generativelanguage.googleapis.com",
    "openrouter": "https://openrouter.ai/api",
}

# Env vars checked per provider, in priority order within the env tier
_PROVIDER_ENV_VARS: dict[str, list[str]] = {
    "anthropic": ["TYPEC_UPSTREAM_ANTHROPIC", "ANTHROPIC_BASE_URL"],
    "openai": ["TYPEC_UPSTREAM_OPENAI", "OPENAI_BASE_URL"],
    "gemini": ["TYPEC_UPSTREAM_GEMINI"],
    "openrouter": ["TYPEC_UPSTREAM_OPENROUTER"],
}

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            timeout=httpx.Timeout(120.0),
        )
    return _client


def provider_url(
    provider: str,
    upstream_overrides: dict[str, str] | None = None,
) -> str:
    """Resolve the upstream URL for a provider.

    Priority:
      1. Contract ``upstream.*`` passed as upstream_overrides dict
      2. ``TYPEC_UPSTREAM_{PROVIDER}`` or ``ANTHROPIC_BASE_URL`` / ``OPENAI_BASE_URL`` env vars
      3. Built-in default (api.anthropic.com, api.openai.com, etc.)

    This allows the proxy to chain correctly when the LLM client is configured
    to use a non-Anthropic backend such as DeepSeek, a local model, or any
    OpenAI-compatible endpoint.
    """
    # 1. Contract-level override (highest priority)
    if upstream_overrides:
        url = upstream_overrides.get(provider, "").strip()
        if url:
            return url.rstrip("/")

    # 2. Env var overrides
    for env_key in _PROVIDER_ENV_VARS.get(provider, []):
        val = os.environ.get(env_key, "").strip()
        if val:
            return val.rstrip("/")

    # 3. Built-in default
    return _PROVIDER_DEFAULTS.get(provider, "")


_HOP_BY_HOP: frozenset[str] = frozenset([
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
])


def _forward_headers(raw_request: Request, provider: str) -> dict[str, str]:
    return {
        k.lower(): v
        for k, v in raw_request.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }


async def forward_request(
    provider: str,
    payload: dict,
    raw_request: Request,
    path: str = "",
    upstream_overrides: dict[str, str] | None = None,
) -> httpx.Response:
    client = get_client()
    base = provider_url(provider, upstream_overrides)
    headers = _forward_headers(raw_request, provider)

    if provider == "anthropic":
        url = f"{base}/v1/messages"
    elif provider == "openai":
        url = f"{base}{path}"
    elif provider == "gemini":
        model = payload.get("model", "gemini-pro")
        url = f"{base}/v1beta/models/{model}:generateContent"
    elif provider == "openrouter":
        url = f"{base}{path}"
    else:
        url = f"{base}{path}"

    return await client.post(url, json=payload, headers=headers)


async def forward_raw(
    provider: str,
    path: str,
    raw_request: Request,
    method: str = "POST",
    payload: dict | None = None,
    upstream_overrides: dict[str, str] | None = None,
) -> httpx.Response:
    client = get_client()
    base = provider_url(provider, upstream_overrides)
    headers = _forward_headers(raw_request, provider)
    url = f"{base}{path}"

    if method == "GET":
        return await client.get(url, headers=headers)
    return await client.post(url, json=payload, headers=headers)
