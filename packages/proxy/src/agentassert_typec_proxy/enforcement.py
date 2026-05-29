from __future__ import annotations

from typing import Any

import httpx
import orjson
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from agentassert_typec_core.exceptions import ContractBreachError
from agentassert_typec_core.models.events import PreAction, PostAction
from agentassert_typec_core.monitor.session import SessionMonitor
from agentassert_typec_proxy.forwarder import forward_request
from agentassert_typec_proxy.normalizer.canonical import CanonicalRequest


async def enforce_and_forward(
    canonical: CanonicalRequest,
    monitor: SessionMonitor,
    raw_request: Request,
    provider_path: str = "/v1/messages",
    upstream_overrides: dict[str, str] | None = None,
) -> JSONResponse | StreamingResponse:
    tool_name = _extract_tool_name(canonical)
    pre_event = PreAction(
        session_id=canonical.session_id,
        contract_id=monitor._contract.name,
        tool=tool_name,
        args={"model": canonical.model, "stream": canonical.stream},
    )

    result = monitor.evaluate(pre_event)

    if result.is_deny():
        breach = ContractBreachError(
            violation_name=result.violation_name,
            reason=result.reason,
            tool=tool_name,
            session_id=canonical.session_id,
            contract_id=monitor._contract.name,
        )
        return JSONResponse(
            status_code=400,
            content=breach.to_http_body(),
            headers={
                "X-AgentAssert-Decision": "deny",
                "Content-Type": "application/json",
            },
        )

    if canonical.stream:
        return await _forward_streaming(canonical, monitor, pre_event, raw_request, provider_path, upstream_overrides)

    try:
        provider = canonical.provider
        provider_resp = await forward_request(
            provider=provider,
            payload=canonical.raw_payload,
            raw_request=raw_request,
            path=provider_path,
            upstream_overrides=upstream_overrides,
        )
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": "ProviderError", "detail": str(e)},
            headers={"X-AgentAssert-Decision": "allow"},
        )

    resp_data = _try_parse_json(provider_resp)
    post_event = PostAction(
        session_id=canonical.session_id,
        contract_id=monitor._contract.name,
        tool=tool_name,
        args={"status": provider_resp.status_code},
        state={"response_bytes": len(provider_resp.content)},
        result=resp_data,
    )
    monitor.evaluate(post_event)

    headers = dict(provider_resp.headers)
    headers["X-AgentAssert-Decision"] = "allow"

    return JSONResponse(
        status_code=provider_resp.status_code,
        content=resp_data,
        headers=headers,
    )


async def _forward_streaming(
    canonical: CanonicalRequest,
    monitor: SessionMonitor,
    pre_event: PreAction,
    raw_request: Request,
    provider_path: str,
    upstream_overrides: dict[str, str] | None = None,
) -> StreamingResponse:
    try:
        provider = canonical.provider
        provider_resp = await forward_request(
            provider=provider,
            payload=canonical.raw_payload,
            raw_request=raw_request,
            path=provider_path,
            upstream_overrides=upstream_overrides,
        )
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={"error": "ProviderError", "detail": str(e)},
            headers={"X-AgentAssert-Decision": "allow"},
        )

    async def stream_generator():
        accumulated = ""
        async for chunk in provider_resp.aiter_bytes():
            accumulated += _accumulate_chunk(chunk)
            yield chunk
        post_event = PostAction(
            session_id=canonical.session_id,
            contract_id=monitor._contract.name,
            tool=pre_event.tool,
            args=pre_event.args,
            state={"stream_bytes": len(accumulated)},
        )
        monitor.evaluate(post_event)

    return StreamingResponse(
        stream_generator(),
        status_code=provider_resp.status_code,
        headers={
            "X-AgentAssert-Decision": "allow",
            "X-AgentAssert-Mode": "stream-through",
            "Content-Type": "text/event-stream",
        },
    )


def _extract_tool_name(canonical: CanonicalRequest) -> str:
    if canonical.tool_calls:
        return canonical.tool_calls[-1].name
    return f"{canonical.provider}.chat.completion"


def _try_parse_json(resp: httpx.Response) -> Any:
    try:
        return orjson.loads(resp.content)
    except Exception:
        return {"raw": resp.text[:1000]}


def _accumulate_chunk(chunk: bytes) -> str:
    try:
        return chunk.decode("utf-8", errors="replace")
    except Exception:
        return ""
