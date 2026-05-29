from __future__ import annotations

from typing import Any

from agentassert_typec_proxy.normalizer.canonical import CanonicalRequest
from agentassert_typec_proxy.normalizer.openai_norm import normalize_openai


def normalize_openrouter(payload: dict[str, Any], session_id: str, request_id: str) -> CanonicalRequest:
    req = normalize_openai(payload, session_id, request_id)
    return CanonicalRequest(
        provider="openrouter",
        model=req.model,
        messages=req.messages,
        tool_calls=req.tool_calls,
        stream=req.stream,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        system=req.system,
        raw_payload=payload,
        session_id=session_id,
        request_id=request_id,
    )
