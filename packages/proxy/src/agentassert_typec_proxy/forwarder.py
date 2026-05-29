from __future__ import annotations

import httpx
from fastapi import Request

PROVIDER_URLS = {
    "anthropic": "https://api.anthropic.com",
    "openai": "https://api.openai.com",
    "gemini": "https://generativelanguage.googleapis.com",
    "openrouter": "https://openrouter.ai/api",
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


def provider_url(provider: str, payload: dict | None = None) -> str:
    return PROVIDER_URLS.get(provider, "")


def _forward_headers(raw_request: Request, provider: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for header in ["authorization", "x-api-key", "anthropic-version", "anthropic-beta", "content-type", "openai-beta"]:
        value = raw_request.headers.get(header)
        if value:
            headers[header] = value
    return headers


async def forward_request(
    provider: str,
    payload: dict,
    raw_request: Request,
    path: str = "",
) -> httpx.Response:
    client = get_client()
    base = provider_url(provider)
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
) -> httpx.Response:
    client = get_client()
    base = provider_url(provider)
    headers = _forward_headers(raw_request, provider)
    url = f"{base}{path}"

    if method == "GET":
        return await client.get(url, headers=headers)
    return await client.post(url, json=payload, headers=headers)
