from __future__ import annotations

import uuid

import orjson
from fastapi import APIRouter, Request
from fastapi.responses import Response

from agentassert_typec_proxy.enforcement import enforce_and_forward
from agentassert_typec_proxy.forwarder import forward_raw
from agentassert_typec_proxy.normalizer.anthropic_norm import normalize_anthropic

router = APIRouter()


@router.api_route("/v1/messages", methods=["POST"])
@router.api_route("/v1/messages/{path:path}", methods=["POST"])
async def messages(request: Request, path: str = "") -> Response:
    monitor = request.app.state.monitor
    body = await request.body()
    payload = orjson.loads(body)
    session_id = request.headers.get("X-AgentAssert-Session", str(uuid.uuid4()))
    request_id = str(uuid.uuid4())
    canonical = normalize_anthropic(payload, session_id, request_id)
    return await enforce_and_forward(canonical, monitor, request, "/v1/messages")


@router.api_route("/v1/messages/count_tokens", methods=["POST"])
async def count_tokens(request: Request) -> Response:
    body = await request.body()
    payload = orjson.loads(body)
    return await forward_raw("anthropic", "/v1/messages/count_tokens", request, payload=payload)
