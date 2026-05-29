from __future__ import annotations

import json
from typing import Any

import httpx
import orjson
from fastapi import Request
from fastapi.responses import JSONResponse, StreamingResponse

from agentassert_typec_core.exceptions import ContractBreachError
from agentassert_typec_core.models.decisions import TypeCDecision
from agentassert_typec_core.models.events import PreAction, PostAction, TurnEnd
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
    response_text = _extract_text_content(resp_data)

    post_event = PostAction(
        session_id=canonical.session_id,
        contract_id=monitor._contract.name,
        tool=tool_name,
        args={"status": provider_resp.status_code},
        state={"response_bytes": len(provider_resp.content)},
        result=resp_data,
    )
    monitor.evaluate(post_event)

    # Phase 3: accumulate cost from non-streaming response
    from agentassert_typec_core.evaluator.content_eval import (
        _update_cost,
        _apply_pii_redaction,
        evaluate_pii_filter,
    )
    _update_cost(resp_data, canonical, monitor)

    # Phase 3: PII filter on non-streaming response
    pii_result = evaluate_pii_filter(
        response_text, monitor._compiled, monitor._violations, is_streaming=False
    )
    if pii_result is not None and pii_result.is_deny():
        return JSONResponse(
            status_code=400,
            content={"error": "ContractBreach", "detail": pii_result.reason},
            headers={"X-AgentAssert-Decision": "deny"},
        )
    elif pii_result is not None and pii_result.is_redact():
        redacted_text = _apply_pii_redaction(response_text, monitor._compiled.pii_compiled_patterns)
        resp_data = _inject_redacted_content(resp_data, redacted_text, canonical.provider)

    turn_end = TurnEnd(
        session_id=canonical.session_id,
        contract_id=monitor._contract.name,
        assistant_output=response_text,
    )
    monitor.evaluate(turn_end)
    monitor.schedule_judge_evaluation(response_text, canonical.session_id)

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
            result={"content": accumulated[:4096]},
        )
        monitor.evaluate(post_event)

        # Phase 3: accumulate cost from SSE usage event
        from agentassert_typec_core.evaluator.content_eval import (
            _parse_streaming_usage,
            _update_cost,
            evaluate_pii_filter,
        )
        usage_data = _parse_streaming_usage(accumulated)
        if usage_data:
            _update_cost(usage_data, canonical, monitor)

        # Phase 3: PII filter post-stream (log/warn only — cannot block already-yielded data)
        evaluate_pii_filter(accumulated, monitor._compiled, monitor._violations, is_streaming=True)

        turn_end = TurnEnd(
            session_id=canonical.session_id,
            contract_id=monitor._contract.name,
            assistant_output=accumulated[:4096],
        )
        monitor.evaluate(turn_end)
        monitor.schedule_judge_evaluation(accumulated, canonical.session_id)

    return StreamingResponse(
        stream_generator(),
        status_code=provider_resp.status_code,
        headers={
            "X-AgentAssert-Decision": "allow",
            "X-AgentAssert-Mode": "stream-through",
            "Content-Type": "text/event-stream",
        },
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _extract_text_content(resp_data: Any) -> str:
    """Best-effort extraction of assistant text from a parsed LLM response."""
    if not isinstance(resp_data, dict):
        return ""
    # Anthropic format
    content = resp_data.get("content", [])
    if isinstance(content, list):
        parts = [b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"]
        if parts:
            return " ".join(parts)
    # OpenAI / xAI / OpenRouter format
    choices = resp_data.get("choices", [])
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message", {})
        return msg.get("content", "") or ""
    return ""


def _inject_redacted_content(resp_data: Any, redacted_text: str, provider: str) -> Any:
    """Reconstruct resp_data with redacted text content in-place."""
    if not isinstance(resp_data, dict):
        return resp_data
    import copy
    data = copy.deepcopy(resp_data)

    # Anthropic format
    if "content" in data and isinstance(data["content"], list):
        for block in data["content"]:
            if isinstance(block, dict) and block.get("type") == "text":
                block["text"] = redacted_text
                break
        return data

    # OpenAI / OpenRouter format
    if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
        msg = data["choices"][0].get("message", {})
        if isinstance(msg, dict):
            msg["content"] = redacted_text
        return data

    return data
